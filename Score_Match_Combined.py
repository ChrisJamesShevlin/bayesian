import tkinter as tk
from tkinter import ttk
from math import exp, comb

class ScorelineLayModel:
    def __init__(self, root):
        self.root = root
        self.root.title("Odds Apex")
        self.create_widgets()

        # History for dynamic updating (running xG averages, etc.)
        self.history_length = 10
        self.history = {
            "home_xg": [],
            "away_xg": [],
            "home_sot": [],
            "away_sot": [],
            "home_possession": [],
            "away_possession": []
        }

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

        # Input fields
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
            "Account Balance": tk.DoubleVar(),
            "Market Odds for Current Scoreline": tk.DoubleVar(),
            "Selected Scoreline": tk.StringVar(),
            "Live Odds for Selected Scoreline": tk.DoubleVar(),

            # Match odds
            "Live Odds Home": tk.DoubleVar(),
            "Live Odds Draw": tk.DoubleVar(),
            "Live Odds Away": tk.DoubleVar()
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

        # Output area for insights and recommendations
        self.output_text = tk.Text(self.scrollable_frame, height=30, wrap="word")
        self.output_text.grid(row=row, column=0, columnspan=2, pady=10)

        # Configure text tags for coloring
        self.output_text.tag_configure("insight", foreground="green")
        self.output_text.tag_configure("lay", foreground="red")
        self.output_text.tag_configure("normal", foreground="black")
        # NEW TAG for 'Back' lines in blue
        self.output_text.tag_configure("back", foreground="blue")

        self.output_text.config(state="disabled")

    def reset_fields(self):
        for var in self.fields.values():
            if isinstance(var, tk.DoubleVar):
                var.set(0.0)
            elif isinstance(var, tk.IntVar):
                var.set(0)
            elif isinstance(var, tk.StringVar):
                var.set("")
        self.history = {
            "home_xg": [],
            "away_xg": [],
            "home_sot": [],
            "away_sot": [],
            "home_possession": [],
            "away_possession": []
        }

    # Bayesian predictive probability using Negative Binomial with Gamma prior
    def bayesian_goal_probability(self, expected_lambda, k, r=2):
        p = r / (r + expected_lambda)
        return comb(k + r - 1, k) * (p ** r) * ((1 - p) ** k)

    # Time-decay for the correct score approach (coefficient=0.003)
    def time_decay_adjustment(self, lambda_xg, elapsed_minutes, in_game_xg):
        remaining_minutes = 90 - elapsed_minutes
        base_decay = exp(-0.003 * elapsed_minutes)
        base_decay = max(base_decay, 0.5)
        if remaining_minutes < 10:
            base_decay *= 0.75
        adjusted_lambda = lambda_xg * base_decay
        return max(0.1, adjusted_lambda)

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

    # Use 1/8 Kelly (0.125 * edge) for both correct score and match odds
    def dynamic_kelly(self, edge):
        return max(0, 0.125 * edge)

    def dynamic_expected_lambda(self, team='home'):
        key = "home_xg" if team == 'home' else "away_xg"
        if self.history[key]:
            return sum(self.history[key]) / len(self.history[key])
        return 1.0

    def calculate_all(self):
        f = self.fields
        # Gather inputs
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
        account_balance = f["Account Balance"].get()
        market_odds_current = f["Market Odds for Current Scoreline"].get()
        selected_score_str = f["Selected Scoreline"].get().strip()
        live_selected_odds = f["Live Odds for Selected Scoreline"].get()

        # NEW: Match odds inputs
        live_odds_home = f["Live Odds Home"].get()
        live_odds_draw = f["Live Odds Draw"].get()
        live_odds_away = f["Live Odds Away"].get()

        # Effective balance (ensure non-negative)
        effective_balance = account_balance if account_balance >= 0 else 0

        # Update dynamic history
        self.update_history("home_xg", home_xg)
        self.update_history("away_xg", away_xg)
        self.update_history("home_sot", home_sot)
        self.update_history("away_sot", away_sot)
        self.update_history("home_possession", home_possession)
        self.update_history("away_possession", away_possession)

        remaining_minutes = 90 - elapsed_minutes
        fraction_remaining = max(0.0, remaining_minutes / 90.0)

        ##############################################################################
        # MATCH ODDS CALCULATION (with 70/30 blend)
        ##############################################################################
        lines_mo = ["--- Match Odds Calculation ---"]

        # Compute remaining xG for match odds
        home_xg_remainder_mo = home_xg * fraction_remaining
        away_xg_remainder_mo = away_xg * fraction_remaining

        # Time decay
        lambda_home_mo = self.time_decay_adjustment(home_xg_remainder_mo, elapsed_minutes, in_game_home_xg)
        lambda_away_mo = self.time_decay_adjustment(away_xg_remainder_mo, elapsed_minutes, in_game_away_xg)

        lambda_home_mo, lambda_away_mo = self.adjust_xg_for_scoreline(home_goals, away_goals,
                                                                      lambda_home_mo, lambda_away_mo,
                                                                      elapsed_minutes)

        # pm_component
        pm_component_home = (home_avg_goals_scored / max(0.75, away_avg_goals_conceded))
        pm_component_away = (away_avg_goals_scored / max(0.75, home_avg_goals_conceded))
        lambda_home_mo = (lambda_home_mo * 0.85) + (pm_component_home * 0.15 * fraction_remaining)
        lambda_away_mo = (lambda_away_mo * 0.85) + (pm_component_away * 0.15 * fraction_remaining)

        # Adjust for possession, SOT, corners, etc.
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

        # Blend with historical xG for "momentum"
        dynamic_lambda_home_mo = self.dynamic_expected_lambda('home')
        dynamic_lambda_away_mo = self.dynamic_expected_lambda('away')
        lambda_home_mo = (lambda_home_mo * 0.7) + (dynamic_lambda_home_mo * 0.3)
        lambda_away_mo = (lambda_away_mo * 0.7) + (dynamic_lambda_away_mo * 0.3)

        # Compute probabilities (r=3)
        home_win_prob = 0
        away_win_prob = 0
        draw_prob = 0
        for gh in range(6):
            for ga in range(6):
                prob = (self.bayesian_goal_probability(lambda_home_mo, gh, r=3) *
                        self.bayesian_goal_probability(lambda_away_mo, ga, r=3))
                if home_goals + gh > away_goals + ga:
                    home_win_prob += prob
                elif home_goals + gh < away_goals + ga:
                    away_win_prob += prob
                else:
                    draw_prob += prob

        total_prob_mo = home_win_prob + away_win_prob + draw_prob
        if total_prob_mo > 0:
            home_win_prob /= total_prob_mo
            away_win_prob /= total_prob_mo
            draw_prob /= total_prob_mo

        # Convert live odds to market implied probabilities
        market_home_prob = (1 / live_odds_home) if live_odds_home > 0 else 0
        market_draw_prob = (1 / live_odds_draw) if live_odds_draw > 0 else 0
        market_away_prob = (1 / live_odds_away) if live_odds_away > 0 else 0
        market_total = market_home_prob + market_draw_prob + market_away_prob
        if market_total > 0:
            market_home_prob /= market_total
            market_draw_prob /= market_total
            market_away_prob /= market_total

        # Blend model vs. market (70/30)
        blended_home_prob = 0.7 * home_win_prob + 0.3 * market_home_prob
        blended_draw_prob = 0.7 * draw_prob + 0.3 * market_draw_prob
        blended_away_prob = 0.7 * away_win_prob + 0.3 * market_away_prob

        # Normalize blended
        blended_total = blended_home_prob + blended_draw_prob + blended_away_prob
        if blended_total > 0:
            blended_home_prob /= blended_total
            blended_draw_prob /= blended_total
            blended_away_prob /= blended_total

        # Fair odds from blended
        fair_odds_home = 1 / blended_home_prob if blended_home_prob > 0 else float('inf')
        fair_odds_draw = 1 / blended_draw_prob if blended_draw_prob > 0 else float('inf')
        fair_odds_away = 1 / blended_away_prob if blended_away_prob > 0 else float('inf')

        lines_mo.append(f"Fair Odds - Home: {fair_odds_home:.2f}, Draw: {fair_odds_draw:.2f}, Away: {fair_odds_away:.2f}")
        lines_mo.append(f"Live Odds - Home: {live_odds_home:.2f}, Draw: {live_odds_draw:.2f}, Away: {live_odds_away:.2f}")

        # Helper function to clamp to 10% of balance
        def clamp_to_10pct(val):
            return min(val, effective_balance * 0.10)

        # Compare fair vs. live for each outcome
        # 1) Home
        if fair_odds_home > live_odds_home > 1:
            edge = (fair_odds_home - live_odds_home) / fair_odds_home
            liability = effective_balance * self.dynamic_kelly(edge)
            liability = clamp_to_10pct(liability)
            lay_stake = liability / (live_odds_home - 1) if (live_odds_home - 1) > 0 else 0
            lines_mo.append(f"Lay Home: Edge {edge:.2%}, Liability {liability:.2f}, Stake {lay_stake:.2f}")
        elif fair_odds_home < live_odds_home:
            edge = (live_odds_home - fair_odds_home) / fair_odds_home
            stake = effective_balance * self.dynamic_kelly(edge)
            stake = clamp_to_10pct(stake)
            profit = stake * (live_odds_home - 1)
            lines_mo.append(f"Back Home: Edge {edge:.2%}, Stake {stake:.2f}, Profit {profit:.2f}")
        else:
            lines_mo.append("Home: No clear edge.")

        # 2) Draw
        if fair_odds_draw > live_odds_draw > 1:
            edge = (fair_odds_draw - live_odds_draw) / fair_odds_draw
            liability = effective_balance * self.dynamic_kelly(edge)
            liability = clamp_to_10pct(liability)
            lay_stake = liability / (live_odds_draw - 1) if (live_odds_draw - 1) > 0 else 0
            lines_mo.append(f"Lay Draw: Edge {edge:.2%}, Liability {liability:.2f}, Stake {lay_stake:.2f}")
        elif fair_odds_draw < live_odds_draw:
            edge = (live_odds_draw - fair_odds_draw) / fair_odds_draw
            stake = effective_balance * self.dynamic_kelly(edge)
            stake = clamp_to_10pct(stake)
            profit = stake * (live_odds_draw - 1)
            lines_mo.append(f"Back Draw: Edge {edge:.2%}, Stake {stake:.2f}, Profit {profit:.2f}")
        else:
            lines_mo.append("Draw: No clear edge.")

        # 3) Away
        if fair_odds_away > live_odds_away > 1:
            edge = (fair_odds_away - live_odds_away) / fair_odds_away
            liability = effective_balance * self.dynamic_kelly(edge)
            liability = clamp_to_10pct(liability)
            lay_stake = liability / (live_odds_away - 1) if (live_odds_away - 1) > 0 else 0
            lines_mo.append(f"Lay Away: Edge {edge:.2%}, Liability {liability:.2f}, Stake {lay_stake:.2f}")
        elif fair_odds_away < live_odds_away:
            edge = (live_odds_away - fair_odds_away) / fair_odds_away
            stake = effective_balance * self.dynamic_kelly(edge)
            stake = clamp_to_10pct(stake)
            profit = stake * (live_odds_away - 1)
            lines_mo.append(f"Back Away: Edge {edge:.2%}, Stake {stake:.2f}, Profit {profit:.2f}")
        else:
            lines_mo.append("Away: No clear edge.")

        ##############################################################################
        # SCORELINE PROBABILITY CALCULATION
        ##############################################################################
        lines_exp_goals = ["--- Expected Goals Betting Insights ---"]

        # Fraction of xG left
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

        # Momentum with historical xG
        blend_weight = 0.7
        dynamic_lambda_home = self.dynamic_expected_lambda('home')
        dynamic_lambda_away = self.dynamic_expected_lambda('away')
        lambda_home = blend_weight * lambda_home + (1 - blend_weight) * dynamic_lambda_home
        lambda_away = blend_weight * lambda_away + (1 - blend_weight) * dynamic_lambda_away

        # Calculate expected goals left
        expected_goals_home = lambda_home
        expected_goals_away = lambda_away
        total_expected_goals = expected_goals_home + expected_goals_away

        lines_exp_goals.append(f"Expected Goals Left - Home: {expected_goals_home:.2f}")
        lines_exp_goals.append(f"Expected Goals Left - Away: {expected_goals_away:.2f}")
        lines_exp_goals.append(f"Total Expected Goals Left: {total_expected_goals:.2f}")

        # Build dictionary of final score probabilities
        score_probabilities = {}
        for gh in range(6):
            for ga in range(6):
                prob = (self.bayesian_goal_probability(lambda_home, gh) *
                        self.bayesian_goal_probability(lambda_away, ga))
                final_score = (home_goals + gh, away_goals + ga)
                score_probabilities[final_score] = score_probabilities.get(final_score, 0) + prob

        # Blend in Market Odds for the Current Scoreline
        current_score = (home_goals, away_goals)
        if market_odds_current > 0 and current_score in score_probabilities:
            market_current_prob = 1 / market_odds_current
            model_current_prob = score_probabilities[current_score]
            blended_prob = 0.7 * model_current_prob + 0.3 * market_current_prob
            score_probabilities[current_score] = blended_prob
            total_prob = sum(score_probabilities.values())
            if total_prob > 0:
                for key in score_probabilities:
                    score_probabilities[key] /= total_prob

        # Scoreline Probability Insights
        lines_insight = ["--- Scoreline Probability Insights ---"]
        sorted_scores = sorted(score_probabilities.items(), key=lambda item: item[1], reverse=True)
        if sorted_scores:
            for score, prob in sorted_scores[:5]:
                fair_odds = 1/prob if prob > 0 else float('inf')
                lines_insight.append(f"Scoreline {score[0]}-{score[1]}: {prob:.2%} (Fair Odds: {fair_odds:.2f})")
        else:
            lines_insight.append("Insufficient data for scoreline prediction.")

        # Lay Recommendation for Selected Scoreline
        lines_selected = ["--- Selected Scoreline Lay Recommendation ---"]
        try:
            selected_score = tuple(map(int, selected_score_str.split('-')))
        except Exception:
            selected_score = None

        if selected_score and selected_score in score_probabilities:
            selected_prob = score_probabilities[selected_score]
            fair_odds_selected = 1/selected_prob if selected_prob > 0 else float('inf')
            lines_selected.append(
                f"Selected Scoreline {selected_score[0]}-{selected_score[1]}: "
                f"Probability: {selected_prob:.2%}, Fair Odds: {fair_odds_selected:.2f}"
            )
            if live_selected_odds > 0 and fair_odds_selected > live_selected_odds:
                edge = (fair_odds_selected - live_selected_odds) / fair_odds_selected
                base_liability = effective_balance * self.dynamic_kelly(edge)
                liability = min(base_liability, effective_balance * 0.10)
                lay_stake = 0.0
                if (live_selected_odds - 1) > 0:
                    lay_stake = liability / (live_selected_odds - 1)
                lines_selected.append(
                    f"Recommended Lay Bet: Edge: {edge:.2%}, Liability: {liability:.2f}, Lay Stake: {lay_stake:.2f}"
                )
            else:
                lines_selected.append("No lay edge found (fair odds not higher than live odds).")
        else:
            lines_selected.append("Selected scoreline not found in calculated probabilities.")

        ##############################################################################
        # Combine and Output
        ##############################################################################
        combined_lines = []
        # 1) Match Odds first
        combined_lines.extend(lines_mo)
        combined_lines.append("")
        # 2) Expected Goals & Scoreline Insights
        combined_lines.extend(lines_exp_goals)
        combined_lines.append("")
        combined_lines.extend(lines_insight)
        combined_lines.append("")
        # 3) Selected Scoreline
        combined_lines.extend(lines_selected)
        combined_lines.append("")

        self.output_text.config(state="normal")
        self.output_text.delete("1.0", tk.END)

        for line in combined_lines:
            if line.startswith("---"):
                self.output_text.insert(tk.END, line + "\n", "insight")
            elif "Lay" in line:
                self.output_text.insert(tk.END, line + "\n", "lay")
            elif "Back" in line:  # <-- New check for "Back"
                self.output_text.insert(tk.END, line + "\n", "back")
            else:
                self.output_text.insert(tk.END, line + "\n", "normal")

        self.output_text.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = ScorelineLayModel(root)
    root.mainloop()
