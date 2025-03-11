import tkinter as tk
from tkinter import ttk
from math import exp, comb

class CombinedFootballBettingModel:
    def __init__(self, root):
        self.root = root
        self.root.title("Odds Apex")
        self.create_widgets()
        # History maintained for potential future use
        self.history = {
            "home_xg": [],
            "away_xg": [],
            "home_sot": [],
            "away_sot": [],
            "home_possession": [],
            "away_possession": []
        }
        self.history_length = 10  # last 10 updates

    def create_widgets(self):
        # Create a scrollable frame
        self.canvas = tk.Canvas(self.root)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Combined fields from both models
        self.fields = {
            "Home Avg Goals Scored": tk.DoubleVar(),
            "Home Avg Goals Conceded": tk.DoubleVar(),
            "Away Avg Goals Scored": tk.DoubleVar(),
            "Away Avg Goals Conceded": tk.DoubleVar(),
            "Home Xg": tk.DoubleVar(),
            "Away Xg": tk.DoubleVar(),
            "Elapsed Minutes": tk.DoubleVar(),
            "Home Goals": tk.IntVar(),
            "Away Goals": tk.IntVar(),
            "In-Game Home Xg": tk.DoubleVar(),
            "In-Game Away Xg": tk.DoubleVar(),
            "Home Possession %": tk.DoubleVar(),
            "Away Possession %": tk.DoubleVar(),
            "Home Shots on Target": tk.IntVar(),
            "Away Shots on Target": tk.IntVar(),
            "Home Opp Box Touches": tk.DoubleVar(),
            "Away Opp Box Touches": tk.DoubleVar(),
            "Home Corners": tk.DoubleVar(),
            "Away Corners": tk.DoubleVar(),
            "Live Next Goal Odds": tk.DoubleVar(),
            "Live Odds Home": tk.DoubleVar(),
            "Live Odds Draw": tk.DoubleVar(),
            "Live Odds Away": tk.DoubleVar(),
            "Account Balance": tk.DoubleVar()
        }
        row = 0
        for field, var in self.fields.items():
            label = ttk.Label(self.scrollable_frame, text=field)
            label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            entry = ttk.Entry(self.scrollable_frame, textvariable=var)
            entry.grid(row=row, column=1, padx=5, pady=5)
            row += 1

        # Calculate and Reset buttons
        calc_button = ttk.Button(self.scrollable_frame, text="Calculate", command=self.calculate_all)
        calc_button.grid(row=row, column=0, columnspan=2, pady=10)
        row += 1

        reset_button = ttk.Button(self.scrollable_frame, text="Reset Fields", command=self.reset_fields)
        reset_button.grid(row=row, column=0, columnspan=2, pady=10)
        row += 1

        # Output area for both betting insights and Match Odds calculations
        self.output_text = tk.Text(self.scrollable_frame, height=20, wrap="word")
        self.output_text.grid(row=row, column=0, columnspan=2, pady=10)
        # Configure color tags
        self.output_text.tag_configure("insight", foreground="green")
        self.output_text.tag_configure("lay", foreground="red")
        self.output_text.tag_configure("back", foreground="blue")
        self.output_text.tag_configure("normal", foreground="black")
        self.output_text.config(state="disabled")

    def reset_fields(self):
        for var in self.fields.values():
            if isinstance(var, tk.DoubleVar):
                var.set(0.0)
            elif isinstance(var, tk.IntVar):
                var.set(0)
        self.history = {
            "home_xg": [],
            "away_xg": [],
            "home_sot": [],
            "away_sot": [],
            "home_possession": [],
            "away_possession": []
        }

    # ----- Bayesian Predictive Goal Probability -----
    def bayesian_goal_probability(self, expected_lambda, k, r=3):
        """
        Bayesian predictive probability for scoring k goals.
        With a Gamma prior on λ (shape parameter r), the predictive distribution becomes Negative Binomial:
            P(k) = comb(k+r-1, k) * (r/(r+expected_lambda))^r * (expected_lambda/(r+expected_lambda))^k
        """
        p = r / (r + expected_lambda)
        return comb(k + r - 1, k) * (p ** r) * ((1 - p) ** k)

    def time_decay_adjustment(self, lambda_xg, elapsed_minutes, in_game_xg):
        """
        Applies a time-decay factor to the expected goals for the remainder.
        Uses a gentler decay factor.
        """
        remaining_minutes = 90 - elapsed_minutes
        base_decay = exp(-0.005 * elapsed_minutes)
        base_decay = max(base_decay, 0.4)
        if remaining_minutes < 10:
            base_decay *= 0.75
        adjusted_lambda = lambda_xg * base_decay
        adjusted_lambda = max(0.1, adjusted_lambda)
        return adjusted_lambda

    def adjust_xg_for_scoreline(self, home_goals, away_goals, lambda_home, lambda_away, elapsed_minutes):
        goal_diff = home_goals - away_goals
        if goal_diff == 1:
            lambda_home *= 0.9
            lambda_away *= 1.2
        elif goal_diff == -1:
            lambda_home *= 1.2
            lambda_away *= 0.9
        elif abs(goal_diff) >= 2:
            if goal_diff > 0:
                lambda_home *= 0.8
                lambda_away *= 1.3
            else:
                lambda_home *= 0.8
                lambda_away *= 0.8
        if elapsed_minutes > 75 and abs(goal_diff) >= 1:
            if goal_diff > 0:
                lambda_home *= 0.85
                lambda_away *= 1.15
            else:
                lambda_home *= 1.15
                lambda_away *= 0.85
        return lambda_home, lambda_away

    def update_history(self, key, value):
        if key not in self.history:
            self.history[key] = []
        if len(self.history[key]) >= self.history_length:
            self.history[key].pop(0)
        self.history[key].append(value)

    def dynamic_kelly(self, edge):
        kelly_fraction = 0.25 * edge
        return max(0, kelly_fraction)

    def dynamic_expected_lambda(self, team='home'):
        """
        Compute the running average of xG for a team from memory.
        This provides a dynamic prior that updates as new data comes in.
        """
        key = "home_xg" if team == 'home' else "away_xg"
        if self.history[key]:
            return sum(self.history[key]) / len(self.history[key])
        return 1.0  # default value if no history

    # ----- Combined Calculation -----
    def calculate_all(self):
        f = self.fields
        home_xg = f["Home Xg"].get()
        away_xg = f["Away Xg"].get()
        elapsed_minutes = f["Elapsed Minutes"].get()
        home_goals = f["Home Goals"].get()
        away_goals = f["Away Goals"].get()
        in_game_home_xg = f["In-Game Home Xg"].get()
        in_game_away_xg = f["In-Game Away Xg"].get()
        home_possession = f["Home Possession %"].get()
        away_possession = f["Away Possession %"].get()
        home_avg_goals_scored = f["Home Avg Goals Scored"].get()
        home_avg_goals_conceded = f["Home Avg Goals Conceded"].get()
        away_avg_goals_scored = f["Away Avg Goals Scored"].get()
        away_avg_goals_conceded = f["Away Avg Goals Conceded"].get()
        home_sot = f["Home Shots on Target"].get()
        away_sot = f["Away Shots on Target"].get()
        home_op_box_touches = f["Home Opp Box Touches"].get()
        away_op_box_touches = f["Away Opp Box Touches"].get()
        home_corners = f["Home Corners"].get()
        away_corners = f["Away Corners"].get()
        live_next_goal_odds = f["Live Next Goal Odds"].get()  # Not used in insights now
        live_odds_home = f["Live Odds Home"].get()
        live_odds_draw = f["Live Odds Draw"].get()
        live_odds_away = f["Live Odds Away"].get()
        account_balance = f["Account Balance"].get()

        # Update memory with current values
        self.update_history("home_xg", home_xg)
        self.update_history("away_xg", away_xg)
        self.update_history("home_sot", home_sot)
        self.update_history("away_sot", away_sot)
        self.update_history("home_possession", home_possession)
        self.update_history("away_possession", away_possession)

        remaining_minutes = 90 - elapsed_minutes
        fraction_remaining = max(0.0, remaining_minutes / 90.0)

        # --- Next Correct Scoreline Insights using Bayesian Prediction ---
        # Calculate the lambda values for the remaining match using in-play and pre-game metrics.
        home_xg_remainder = home_xg * fraction_remaining
        away_xg_remainder = away_xg * fraction_remaining

        lambda_home = self.time_decay_adjustment(home_xg_remainder, elapsed_minutes, in_game_home_xg)
        lambda_away = self.time_decay_adjustment(away_xg_remainder, elapsed_minutes, in_game_away_xg)

        lambda_home, lambda_away = self.adjust_xg_for_scoreline(home_goals, away_goals, lambda_home, lambda_away, elapsed_minutes)

        pm_component_home = (home_avg_goals_scored / max(0.75, away_avg_goals_conceded))
        pm_component_away = (away_avg_goals_scored / max(0.75, home_avg_goals_conceded))
        lambda_home = (lambda_home * 0.85) + (pm_component_home * 0.15 * fraction_remaining)
        lambda_away = (lambda_away * 0.85) + (pm_component_away * 0.15 * fraction_remaining)

        lambda_home *= 1 + ((home_possession - 50) / 200) * fraction_remaining
        lambda_away *= 1 + ((away_possession - 50) / 200) * fraction_remaining

        if in_game_home_xg > 1.2:
            lambda_home *= (1 + 0.15 * fraction_remaining)
        if in_game_away_xg > 1.2:
            lambda_away *= (1 + 0.15 * fraction_remaining)

        lambda_home *= 1 + (home_sot / 20) * fraction_remaining
        lambda_away *= 1 + (away_sot / 20) * fraction_remaining

        lambda_home *= 1 + ((home_op_box_touches - 20) / 200) * fraction_remaining
        lambda_away *= 1 + ((away_op_box_touches - 20) / 200) * fraction_remaining

        lambda_home *= 1 + ((home_corners - 4) / 50) * fraction_remaining
        lambda_away *= 1 + ((away_corners - 4) / 50) * fraction_remaining

        # Calculate the probability distribution over final scorelines
        # (by considering additional goals from 0 to 3 for each team)
        score_probabilities = {}
        for gh in range(4):
            for ga in range(4):
                prob = self.bayesian_goal_probability(lambda_home, gh) * self.bayesian_goal_probability(lambda_away, ga)
                final_score = (home_goals + gh, away_goals + ga)
                score_probabilities[final_score] = score_probabilities.get(final_score, 0) + prob

        # Sort scorelines by probability (descending order)
        sorted_scores = sorted(score_probabilities.items(), key=lambda item: item[1], reverse=True)

        lines_insight = []
        lines_insight.append("--- Next Correct Scoreline Insights ---")
        if sorted_scores:
            top_scores = sorted_scores[:2]  # Get the two most likely scorelines
            for score, prob in top_scores:
                lines_insight.append(f"Scoreline {score[0]}-{score[1]}: {prob:.2%}")
        else:
            lines_insight.append("Insufficient data for scoreline prediction.")

        # --- Match Odds Calculation (unchanged) ---
        home_xg_remainder_mo = home_xg * fraction_remaining
        away_xg_remainder_mo = away_xg * fraction_remaining

        lambda_home_mo = self.time_decay_adjustment(home_xg_remainder_mo, elapsed_minutes, in_game_home_xg)
        lambda_away_mo = self.time_decay_adjustment(away_xg_remainder_mo, elapsed_minutes, in_game_away_xg)

        lambda_home_mo, lambda_away_mo = self.adjust_xg_for_scoreline(home_goals, away_goals, lambda_home_mo, lambda_away_mo, elapsed_minutes)

        pm_component_home_mo = (home_avg_goals_scored / max(0.75, away_avg_goals_conceded))
        pm_component_away_mo = (away_avg_goals_scored / max(0.75, home_avg_goals_conceded))
        lambda_home_mo = (lambda_home_mo * 0.85) + (pm_component_home_mo * 0.15 * fraction_remaining)
        lambda_away_mo = (lambda_away_mo * 0.85) + (pm_component_away_mo * 0.15 * fraction_remaining)

        lambda_home_mo *= 1 + ((home_possession - 50) / 200) * fraction_remaining
        lambda_away_mo *= 1 + ((away_possession - 50) / 200) * fraction_remaining

        if in_game_home_xg > 1.2:
            lambda_home_mo *= (1 + 0.15 * fraction_remaining)
        if in_game_away_xg > 1.2:
            lambda_away_mo *= (1 + 0.15 * fraction_remaining)

        lambda_home_mo *= 1 + (home_sot / 20) * fraction_remaining
        lambda_away_mo *= 1 + (away_sot / 20) * fraction_remaining

        lambda_home_mo *= 1 + ((home_op_box_touches - 20) / 200) * fraction_remaining
        lambda_away_mo *= 1 + ((away_op_box_touches - 20) / 200) * fraction_remaining

        lambda_home_mo *= 1 + ((home_corners - 4) / 50) * fraction_remaining
        lambda_away_mo *= 1 + ((away_corners - 4) / 50) * fraction_remaining

        # --- Dynamic Bayesian Updating using Memory ---
        dynamic_lambda_home = (lambda_home_mo + self.dynamic_expected_lambda('home')) / 2
        dynamic_lambda_away = (lambda_away_mo + self.dynamic_expected_lambda('away')) / 2

        home_win_prob = 0
        away_win_prob = 0
        draw_prob = 0

        # Use the Bayesian (Negative Binomial) predictive probabilities
        for gh in range(6):
            for ga in range(6):
                prob = (self.bayesian_goal_probability(dynamic_lambda_home, gh) *
                        self.bayesian_goal_probability(dynamic_lambda_away, ga))
                if home_goals + gh > away_goals + ga:
                    home_win_prob += prob
                elif home_goals + gh < away_goals + ga:
                    away_win_prob += prob
                else:
                    draw_prob += prob

        total = home_win_prob + away_win_prob + draw_prob
        if total > 0:
            home_win_prob /= total
            away_win_prob /= total
            draw_prob /= total

        model_home_prob = home_win_prob
        model_draw_prob = draw_prob
        model_away_prob = away_win_prob

        market_home_prob = 1 / live_odds_home if live_odds_home > 0 else 0
        market_draw_prob = 1 / live_odds_draw if live_odds_draw > 0 else 0
        market_away_prob = 1 / live_odds_away if live_odds_away > 0 else 0

        total_market = market_home_prob + market_draw_prob + market_away_prob
        if total_market > 0:
            market_home_prob /= total_market
            market_draw_prob /= total_market
            market_away_prob /= total_market

        blend_weight = 0.7
        final_home_prob = blend_weight * model_home_prob + (1 - blend_weight) * market_home_prob
        final_draw_prob = blend_weight * model_draw_prob + (1 - blend_weight) * market_draw_prob
        final_away_prob = blend_weight * model_away_prob + (1 - blend_weight) * market_away_prob

        total_final = final_home_prob + final_draw_prob + final_away_prob
        if total_final > 0:
            final_home_prob /= total_final
            final_draw_prob /= total_final
            final_away_prob /= total_final

        fair_odds_home = 1 / final_home_prob if final_home_prob > 0 else float('inf')
        fair_odds_draw = 1 / final_draw_prob if final_draw_prob > 0 else float('inf')
        fair_odds_away = 1 / final_away_prob if final_away_prob > 0 else float('inf')

        lines_mo = []
        lines_mo.append("--- Match Odds Calculation ---")
        lines_mo.append(f"Fair Odds - Home: {fair_odds_home:.2f}, Draw: {fair_odds_draw:.2f}, Away: {fair_odds_away:.2f}")
        lines_mo.append(f"Live Odds - Home: {live_odds_home:.2f}, Draw: {live_odds_draw:.2f}, Away: {live_odds_away:.2f}")

        def clamp_to_10pct(value):
            return min(value, account_balance * 0.10)

        if fair_odds_home > live_odds_home:
            edge = (fair_odds_home - live_odds_home) / fair_odds_home
            liability = account_balance * self.dynamic_kelly(edge)
            liability = clamp_to_10pct(liability)
            lay_stake = liability / (live_odds_home - 1) if (live_odds_home - 1) > 0 else 0
            lines_mo.append(f"Lay Home: Edge: {edge:.2%}, Liability: {liability:.2f}, Lay Stake: {lay_stake:.2f}")
        elif fair_odds_home < live_odds_home:
            edge = (live_odds_home - fair_odds_home) / fair_odds_home
            stake = account_balance * self.dynamic_kelly(edge)
            stake = clamp_to_10pct(stake)
            profit = stake * (live_odds_home - 1)
            lines_mo.append(f"Back Home: Edge: {edge:.2%}, Stake: {stake:.2f}, Profit: {profit:.2f}")
        else:
            lines_mo.append("Home: No clear edge.")

        if fair_odds_draw > live_odds_draw:
            edge = (fair_odds_draw - live_odds_draw) / fair_odds_draw
            liability = account_balance * self.dynamic_kelly(edge)
            liability = clamp_to_10pct(liability)
            lay_stake = liability / (live_odds_draw - 1) if (live_odds_draw - 1) > 0 else 0
            lines_mo.append(f"Lay Draw: Edge: {edge:.2%}, Liability: {liability:.2f}, Lay Stake: {lay_stake:.2f}")
        elif fair_odds_draw < live_odds_draw:
            edge = (live_odds_draw - fair_odds_draw) / fair_odds_draw
            stake = account_balance * self.dynamic_kelly(edge)
            stake = clamp_to_10pct(stake)
            profit = stake * (live_odds_draw - 1)
            lines_mo.append(f"Back Draw: Edge: {edge:.2%}, Stake: {stake:.2f}, Profit: {profit:.2f}")
        else:
            lines_mo.append("Draw: No clear edge.")

        if fair_odds_away > live_odds_away:
            edge = (fair_odds_away - live_odds_away) / fair_odds_away
            liability = account_balance * self.dynamic_kelly(edge)
            liability = clamp_to_10pct(liability)
            lay_stake = liability / (live_odds_away - 1) if (live_odds_away - 1) > 0 else 0
            lines_mo.append(f"Lay Away: Edge: {edge:.2%}, Liability: {liability:.2f}, Lay Stake: {lay_stake:.2f}")
        elif fair_odds_away < live_odds_away:
            edge = (live_odds_away - fair_odds_away) / fair_odds_away
            stake = account_balance * self.dynamic_kelly(edge)
            stake = clamp_to_10pct(stake)
            profit = stake * (live_odds_away - 1)
            lines_mo.append(f"Back Away: Edge: {edge:.2%}, Stake: {stake:.2f}, Profit: {profit:.2f}")
        else:
            lines_mo.append("Away: No clear edge.")

        combined_lines = []
        combined_lines.extend(lines_insight)
        combined_lines.append("")
        combined_lines.extend(lines_mo)
        combined_lines.append("")

        self.output_text.config(state="normal")
        self.output_text.delete("1.0", tk.END)

        for line in combined_lines:
            if line.startswith("--- Next Correct Scoreline Insights"):
                self.output_text.insert(tk.END, line + "\n", "insight")
            elif "Lay " in line:
                self.output_text.insert(tk.END, line + "\n", "lay")
            elif "Back " in line:
                self.output_text.insert(tk.END, line + "\n", "back")
            else:
                self.output_text.insert(tk.END, line + "\n", "normal")

        self.output_text.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = CombinedFootballBettingModel(root)
    root.mainloop()
