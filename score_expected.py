import tkinter as tk
from tkinter import ttk
from math import exp, comb

class ScorelineLayModel:
    def __init__(self, root):
        self.root = root
        self.root.title("Scoreline Lay Model")
        self.create_widgets()
        # History for dynamic updating (running xG averages, etc.)
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

        # Input fields.
        # Removed match odds inputs for Home Win, Draw, Away Win.
        # We still keep "Market Odds for Current Scoreline" for blending the current score probability,
        # plus "Selected Scoreline" and "Live Odds for Selected Scoreline" for the lay recommendation.
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
            "Locked Profit": tk.DoubleVar(),          # Profit already secured
            "Account Balance": tk.DoubleVar(),
            "Cumulative Loss": tk.DoubleVar(),        # For loss recovery
            "Market Odds for Current Scoreline": tk.DoubleVar(),  # For blending current score probability
            "Selected Scoreline": tk.StringVar(),      # e.g., "0-1"
            "Live Odds for Selected Scoreline": tk.DoubleVar()   # Live odds for that selected scoreline
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
        self.output_text.tag_configure("insight", foreground="green")
        self.output_text.tag_configure("lay", foreground="red")
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

    # Bayesian predictive probability using Negative Binomial with Gamma prior
    def bayesian_goal_probability(self, expected_lambda, k, r=2):
        p = r / (r + expected_lambda)
        return comb(k + r - 1, k) * (p ** r) * ((1 - p) ** k)

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

    # Use 1/8 Kelly (0.125 * edge)
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
        locked_profit = f["Locked Profit"].get()
        account_balance = f["Account Balance"].get()
        cumulative_loss = f["Cumulative Loss"].get()
        market_odds_current = f["Market Odds for Current Scoreline"].get()
        selected_score_str = f["Selected Scoreline"].get().strip()
        live_selected_odds = f["Live Odds for Selected Scoreline"].get()

        # Effective balance: account balance minus locked profit.
        effective_balance = account_balance - locked_profit
        if effective_balance < 0:
            effective_balance = 0

        # Update dynamic history
        self.update_history("home_xg", home_xg)
        self.update_history("away_xg", away_xg)
        self.update_history("home_sot", home_sot)
        self.update_history("away_sot", away_sot)
        self.update_history("home_possession", home_possession)
        self.update_history("away_possession", away_possession)

        remaining_minutes = 90 - elapsed_minutes
        fraction_remaining = max(0.0, remaining_minutes / 90.0)

        # --- Scoreline Probability Calculation ---
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

        # --- Incorporate Momentum via Blending with Historical Averages ---
        blend_weight = 0.7  # 70% current, 30% historical
        dynamic_lambda_home = self.dynamic_expected_lambda('home')
        dynamic_lambda_away = self.dynamic_expected_lambda('away')
        lambda_home = blend_weight * lambda_home + (1 - blend_weight) * dynamic_lambda_home
        lambda_away = blend_weight * lambda_away + (1 - blend_weight) * dynamic_lambda_away

        # --- Calculate Expected Goals Left ---
        expected_goals_home = lambda_home
        expected_goals_away = lambda_away
        total_expected_goals = expected_goals_home + expected_goals_away

        # --- Build Dictionary of Final Score Probabilities ---
        score_probabilities = {}
        for gh in range(6):
            for ga in range(6):
                prob = (self.bayesian_goal_probability(lambda_home, gh) *
                        self.bayesian_goal_probability(lambda_away, ga))
                final_score = (home_goals + gh, away_goals + ga)
                score_probabilities[final_score] = score_probabilities.get(final_score, 0) + prob

        # --- Blend in Market Odds for the Current Scoreline ---
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

        # --- Prepare Expected Goals Betting Insights ---
        lines_exp_goals = ["--- Expected Goals Betting Insights ---"]
        lines_exp_goals.append(f"Expected Goals Left - Home: {expected_goals_home:.2f}")
        lines_exp_goals.append(f"Expected Goals Left - Away: {expected_goals_away:.2f}")
        lines_exp_goals.append(f"Total Expected Goals Left: {total_expected_goals:.2f}")

        # --- Prepare Scoreline Probability Insights ---
        sorted_scores = sorted(score_probabilities.items(), key=lambda item: item[1], reverse=True)
        lines_insight = ["--- Scoreline Probability Insights ---"]
        if sorted_scores:
            for score, prob in sorted_scores[:5]:
                fair_odds = 1/prob if prob > 0 else float('inf')
                lines_insight.append(f"Scoreline {score[0]}-{score[1]}: {prob:.2%} (Fair Odds: {fair_odds:.2f})")
        else:
            lines_insight.append("Insufficient data for scoreline prediction.")

        # --- Lay Recommendation for Selected Scoreline ---
        lines_selected = ["--- Selected Scoreline Lay Recommendation ---"]
        try:
            selected_score = tuple(map(int, selected_score_str.split('-')))
        except Exception:
            selected_score = None

        if selected_score and selected_score in score_probabilities:
            selected_prob = score_probabilities[selected_score]
            fair_odds_selected = 1/selected_prob if selected_prob > 0 else float('inf')
            lines_selected.append(
                f"Selected Scoreline {selected_score[0]}-{selected_score[1]}: Probability: {selected_prob:.2%}, Fair Odds: {fair_odds_selected:.2f}"
            )
            if live_selected_odds > 0 and fair_odds_selected > live_selected_odds:
                edge = (fair_odds_selected - live_selected_odds) / fair_odds_selected
                recovery_factor = 0.5
                recovery_multiplier = 1 + (abs(cumulative_loss) / account_balance) * recovery_factor if account_balance > 0 else 1
                base_liability = effective_balance * self.dynamic_kelly(edge)
                liability = base_liability * recovery_multiplier
                liability = min(liability, effective_balance * 0.10)
                lay_stake = liability / (live_selected_odds - 1) if (live_selected_odds - 1) > 0 else 0
                lines_selected.append(
                    f"Recommended Lay Bet: Edge: {edge:.2%}, Liability: {liability:.2f}, Lay Stake: {lay_stake:.2f}"
                )
            else:
                lines_selected.append("No lay edge found (fair odds not higher than live odds).")
        else:
            lines_selected.append("Selected scoreline not found in calculated probabilities.")

        # --- Combine and Output ---
        combined_lines = []
        combined_lines.extend(lines_exp_goals)
        combined_lines.append("")
        combined_lines.extend(lines_insight)
        combined_lines.append("")
        combined_lines.extend(lines_selected)
        combined_lines.append("")

        self.output_text.config(state="normal")
        self.output_text.delete("1.0", tk.END)
        for line in combined_lines:
            if line.startswith("---"):
                self.output_text.insert(tk.END, line + "\n", "insight")
            elif "Lay" in line:
                self.output_text.insert(tk.END, line + "\n", "lay")
            else:
                self.output_text.insert(tk.END, line + "\n", "normal")
        self.output_text.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = ScorelineLayModel(root)
    root.mainloop()
