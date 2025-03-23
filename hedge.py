import tkinter as tk
from tkinter import ttk
from math import exp, comb

class CombinedFootballHedgeModel:
    def __init__(self, root):
        self.root = root
        self.root.title("Odds Apex - Combined Model")

        # Keep a small history for dynamic xG, if desired
        self.history_length = 10
        self.history = {
            "home_xg": [],
            "away_xg": [],
            "home_sot": [],
            "away_sot": [],
            "home_possession": [],
            "away_possession": []
        }

        # These will store the recommended correct-score lay and the hedge bet on Home
        self.cs_lay_stake = 0.0
        self.cs_liability = 0.0
        self.hedge_stake = 0.0
        self.hedge_odds = 0.0

        self.create_widgets()

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

        # Combined Input Fields
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

            # Match Odds (informational only)
            "Live Odds Home": tk.DoubleVar(),
            "Live Odds Draw": tk.DoubleVar(),
            "Live Odds Away": tk.DoubleVar(),

            # Correct Score Market
            "Market Odds for Current Scoreline": tk.DoubleVar(),
            "Selected Scoreline": tk.StringVar(),
            "Live Odds for Selected Scoreline": tk.DoubleVar(),

            "Account Balance": tk.DoubleVar()
        }
        row = 0
        for field, var in self.fields.items():
            label = ttk.Label(self.scrollable_frame, text=field)
            label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            entry = ttk.Entry(self.scrollable_frame, textvariable=var)
            entry.grid(row=row, column=1, padx=5, pady=5)
            row += 1

        # Calculate and Reset Buttons
        calc_button = ttk.Button(self.scrollable_frame, text="Calculate", command=self.calculate_all)
        calc_button.grid(row=row, column=0, columnspan=2, pady=10)
        row += 1
        reset_button = ttk.Button(self.scrollable_frame, text="Reset Fields", command=self.reset_fields)
        reset_button.grid(row=row, column=0, columnspan=2, pady=10)
        row += 1

        # Output Text area
        self.output_text = tk.Text(self.scrollable_frame, height=45, wrap="word")
        self.output_text.grid(row=row, column=0, columnspan=2, pady=10)
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
        self.cs_lay_stake = 0.0
        self.cs_liability = 0.0
        self.hedge_stake = 0.0
        self.hedge_odds = 0.0

    def update_history(self, key, value):
        if key not in self.history:
            self.history[key] = []
        if len(self.history[key]) >= self.history_length:
            self.history[key].pop(0)
        self.history[key].append(value)

    # Simple 0.25 Kelly for correct score
    def dynamic_kelly(self, edge):
        return max(0, 0.25 * edge)

    def time_decay_adjustment(self, lambda_xg, elapsed_minutes, in_game_xg, coefficient, min_decay):
        remaining_minutes = 90 - elapsed_minutes
        base_decay = exp(-coefficient * elapsed_minutes)
        base_decay = max(base_decay, min_decay)
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

    def bayesian_goal_probability(self, expected_lambda, k, r):
        p = r / (r + expected_lambda)
        return comb(k + r - 1, k) * (p ** r) * ((1 - p) ** k)

    def dynamic_expected_lambda(self, team='home'):
        key = "home_xg" if team == 'home' else "away_xg"
        if self.history[key]:
            return sum(self.history[key]) / len(self.history[key])
        return 1.0

    def calculate_all(self):
        f = self.fields

        # Basic inputs
        home_avg_goals_scored = f["Home Avg Goals Scored"].get()
        home_avg_goals_conceded = f["Home Avg Goals Conceded"].get()
        away_avg_goals_scored = f["Away Avg Goals Scored"].get()
        away_avg_goals_conceded = f["Away Avg Goals Conceded"].get()
        home_xg = f["Home Xg"].get()
        away_xg = f["Away Xg"].get()
        elapsed_minutes = f["Elapsed Minutes"].get()
        home_goals = f["Home Goals"].get()
        away_goals = f["Away Goals"].get()
        in_game_home_xg = f["In-Game Home Xg"].get()
        in_game_away_xg = f["In-Game Away Xg"].get()
        home_possession = f["Home Possession %"].get()
        away_possession = f["Away Possession %"].get()
        home_sot = f["Home Shots on Target"].get()
        away_sot = f["Away Shots on Target"].get()
        home_op_box_touches = f["Home Opp Box Touches"].get()
        away_op_box_touches = f["Away Opp Box Touches"].get()
        home_corners = f["Home Corners"].get()
        away_corners = f["Away Corners"].get()
        account_balance = f["Account Balance"].get()

        # Match odds (informational only)
        live_odds_home = f["Live Odds Home"].get()
        live_odds_draw = f["Live Odds Draw"].get()
        live_odds_away = f["Live Odds Away"].get()

        # Correct score
        market_odds_current = f["Market Odds for Current Scoreline"].get()
        selected_score_str = f["Selected Scoreline"].get().strip()
        live_selected_odds = f["Live Odds for Selected Scoreline"].get()

        # Update xG history if desired
        self.update_history("home_xg", home_xg)
        self.update_history("away_xg", away_xg)
        self.update_history("home_sot", home_sot)
        self.update_history("away_sot", away_sot)
        self.update_history("home_possession", home_possession)
        self.update_history("away_possession", away_possession)

        remaining_minutes = 90 - elapsed_minutes
        fraction_remaining = max(0.0, remaining_minutes / 90.0)

        ################################################
        # A) Informational: Match Odds vs. Fair Odds
        ################################################
        lines_mo = ["--- Match Odds Calculation (Info Only) ---"]

        # We'll just do a quick Bayesian approach for home/draw/away probability
        # but we won't place a stake in the scenario table. This is purely to see
        # if there's "value" in backing or laying any side.

        # 1) Build in-play lambdas for home/away
        # (Parameters chosen arbitrarily to match your first model approach)
        home_xg_remainder_mo = home_xg * fraction_remaining
        away_xg_remainder_mo = away_xg * fraction_remaining

        lambda_home_mo = self.time_decay_adjustment(home_xg_remainder_mo, elapsed_minutes, in_game_home_xg, 0.005, 0.4)
        lambda_away_mo = self.time_decay_adjustment(away_xg_remainder_mo, elapsed_minutes, in_game_away_xg, 0.005, 0.4)
        lambda_home_mo, lambda_away_mo = self.adjust_xg_for_scoreline(home_goals, away_goals, lambda_home_mo, lambda_away_mo, elapsed_minutes)

        pm_component_home = (home_avg_goals_scored / max(0.75, away_avg_goals_conceded))
        pm_component_away = (away_avg_goals_scored / max(0.75, home_avg_goals_conceded))
        lambda_home_mo = (lambda_home_mo * 0.85) + (pm_component_home * 0.15 * fraction_remaining)
        lambda_away_mo = (lambda_away_mo * 0.85) + (pm_component_away * 0.15 * fraction_remaining)

        # Adjust for possession, shots, etc.
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

        # Blend with historical xG
        dynamic_lambda_home = (lambda_home_mo + self.dynamic_expected_lambda('home')) / 2
        dynamic_lambda_away = (lambda_away_mo + self.dynamic_expected_lambda('away')) / 2

        # 2) Bayesian Negative Binomial (r=3)
        home_win_prob = 0
        away_win_prob = 0
        draw_prob = 0
        for gh in range(6):
            for ga in range(6):
                prob = (self.bayesian_goal_probability(dynamic_lambda_home, gh, r=3) *
                        self.bayesian_goal_probability(dynamic_lambda_away, ga, r=3))
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

        # 3) Blend with market
        market_home_prob = 1 / live_odds_home if live_odds_home > 0 else 0
        market_draw_prob = 1 / live_odds_draw if live_odds_draw > 0 else 0
        market_away_prob = 1 / live_odds_away if live_odds_away > 0 else 0
        total_market = market_home_prob + market_draw_prob + market_away_prob
        if total_market > 0:
            market_home_prob /= total_market
            market_draw_prob /= total_market
            market_away_prob /= total_market

        blend_weight = 0.7
        final_home_prob = blend_weight * home_win_prob + (1 - blend_weight) * market_home_prob
        final_draw_prob = blend_weight * draw_prob + (1 - blend_weight) * market_draw_prob
        final_away_prob = blend_weight * away_win_prob + (1 - blend_weight) * market_away_prob
        total_final = final_home_prob + final_draw_prob + final_away_prob
        if total_final > 0:
            final_home_prob /= total_final
            final_draw_prob /= total_final
            final_away_prob /= total_final

        fair_odds_home = 1 / final_home_prob if final_home_prob > 0 else float('inf')
        fair_odds_draw = 1 / final_draw_prob if final_draw_prob > 0 else float('inf')
        fair_odds_away = 1 / final_away_prob if final_away_prob > 0 else float('inf')

        lines_mo.append(f"Fair Odds - Home: {fair_odds_home:.2f}, Draw: {fair_odds_draw:.2f}, Away: {fair_odds_away:.2f}")
        lines_mo.append(f"Live Odds - Home: {live_odds_home:.2f}, Draw: {live_odds_draw:.2f}, Away: {live_odds_away:.2f}")

        # Optional: Note if there's potential value. We do NOT add these to the scenario table.
        def note_value(fair, live, label):
            if fair < live:
                return f"Potential value BACKING {label} (live odds {live:.2f} vs fair {fair:.2f})."
            elif fair > live:
                return f"Potential value LAYING {label} (live odds {live:.2f} vs fair {fair:.2f})."
            else:
                return f"No edge found for {label}."

        lines_mo.append(note_value(fair_odds_home, live_odds_home, "Home"))
        lines_mo.append(note_value(fair_odds_draw, live_odds_draw, "Draw"))
        lines_mo.append(note_value(fair_odds_away, live_odds_away, "Away"))

        ################################################
        # B) Correct Score Probability & Lay
        ################################################
        lines_cs = ["--- Scoreline Probability Insights ---"]

        # 1) Build in-play lambda for correct score (time-decay, etc.)
        home_xg_remainder_cs = home_xg * fraction_remaining
        away_xg_remainder_cs = away_xg * fraction_remaining

        lambda_home_cs = self.time_decay_adjustment(home_xg_remainder_cs, elapsed_minutes, in_game_home_xg, 0.003, 0.5)
        lambda_away_cs = self.time_decay_adjustment(away_xg_remainder_cs, elapsed_minutes, in_game_away_xg, 0.003, 0.5)
        lambda_home_cs, lambda_away_cs = self.adjust_xg_for_scoreline(home_goals, away_goals, lambda_home_cs, lambda_away_cs, elapsed_minutes)

        pm_comp_home = (home_avg_goals_scored / max(0.75, away_avg_goals_conceded))
        pm_comp_away = (away_avg_goals_scored / max(0.75, home_avg_goals_conceded))
        lambda_home_cs = (lambda_home_cs * 0.85) + (pm_comp_home * 0.15 * fraction_remaining)
        lambda_away_cs = (lambda_away_cs * 0.85) + (pm_comp_away * 0.15 * fraction_remaining)

        lambda_home_cs *= 1 + ((home_possession - 50) / 200) * fraction_remaining
        lambda_away_cs *= 1 + ((away_possession - 50) / 200) * fraction_remaining
        if in_game_home_xg > 1.2:
            lambda_home_cs *= (1 + 0.15 * fraction_remaining)
        if in_game_away_xg > 1.2:
            lambda_away_cs *= (1 + 0.15 * fraction_remaining)
        lambda_home_cs *= 1 + (home_sot / 20) * fraction_remaining
        lambda_away_cs *= 1 + (away_sot / 20) * fraction_remaining
        lambda_home_cs *= 1 + ((home_op_box_touches - 20) / 200) * fraction_remaining
        lambda_away_cs *= 1 + ((away_op_box_touches - 20) / 200) * fraction_remaining
        lambda_home_cs *= 1 + ((home_corners - 4) / 50) * fraction_remaining
        lambda_away_cs *= 1 + ((away_corners - 4) / 50) * fraction_remaining

        # Blend with historical xG
        blend_weight_cs = 0.7
        dynamic_lambda_home_cs = self.dynamic_expected_lambda('home')
        dynamic_lambda_away_cs = self.dynamic_expected_lambda('away')
        lambda_home_cs = blend_weight_cs * lambda_home_cs + (1 - blend_weight_cs) * dynamic_lambda_home_cs
        lambda_away_cs = blend_weight_cs * lambda_away_cs + (1 - blend_weight_cs) * dynamic_lambda_away_cs

        # 2) Build the probability distribution for possible (extra) goals
        score_probabilities = {}
        for gh in range(6):
            for ga in range(6):
                prob = (self.bayesian_goal_probability(lambda_home_cs, gh, r=2) *
                        self.bayesian_goal_probability(lambda_away_cs, ga, r=2))
                final_score = (home_goals + gh, away_goals + ga)
                score_probabilities[final_score] = score_probabilities.get(final_score, 0) + prob

        # If you want to blend the market odds for the *current* score
        current_score = (home_goals, away_goals)
        if market_odds_current > 0 and current_score in score_probabilities:
            market_current_prob = 1 / market_odds_current
            model_current_prob = score_probabilities[current_score]
            blended_prob = 0.7 * model_current_prob + 0.3 * market_current_prob
            score_probabilities[current_score] = blended_prob
            # Re-normalize
            total_prob_cs = sum(score_probabilities.values())
            if total_prob_cs > 0:
                for key in score_probabilities:
                    score_probabilities[key] /= total_prob_cs

        # Sort & display top 5
        sorted_scores = sorted(score_probabilities.items(), key=lambda x: x[1], reverse=True)
        if sorted_scores:
            lines_cs.append("Top 5 Scorelines by Probability:")
            for score, prob in sorted_scores[:5]:
                fair_odds_s = (1/prob) if prob > 0 else float('inf')
                lines_cs.append(f"  {score[0]}-{score[1]}: {prob:.2%} (Fair: {fair_odds_s:.2f})")
        else:
            lines_cs.append("No scoreline data available.")

        # 3) Selected Scoreline Lay
        lines_cs.append("")
        lines_cs.append("--- Selected Scoreline Lay ---")
        self.cs_lay_stake = 0.0
        self.cs_liability = 0.0

        try:
            selected_score = tuple(map(int, selected_score_str.split('-')))
        except:
            selected_score = None

        if selected_score and selected_score in score_probabilities:
            prob_sel = score_probabilities[selected_score]
            fair_sel = (1/prob_sel) if prob_sel > 0 else float('inf')
            lines_cs.append(f"Selected Scoreline {selected_score[0]}-{selected_score[1]}: Probability {prob_sel:.2%}, Fair Odds {fair_sel:.2f}")

            if live_selected_odds > 0 and fair_sel > live_selected_odds:
                edge_cs = (fair_sel - live_selected_odds) / fair_sel
                # Quarter Kelly
                base_liability = account_balance * self.dynamic_kelly(edge_cs)
                # clamp to 10% of bank
                base_liability = min(base_liability, account_balance * 0.10)
                stake_cs = 0.0
                if (live_selected_odds - 1) > 0:
                    stake_cs = base_liability / (live_selected_odds - 1)

                lines_cs.append(f"Recommended Lay Bet: Edge {edge_cs:.2%}, Liability {base_liability:.2f}, Lay Stake {stake_cs:.2f}")
                self.cs_liability = base_liability
                self.cs_lay_stake = stake_cs
            else:
                lines_cs.append("No lay edge found (fair odds not higher than live odds).")
        else:
            lines_cs.append("Selected scoreline not found in the probability distribution.")

        ################################################
        # C) Hedging Recommendation
        ################################################
        lines_hedge = ["--- Hedging Recommendation ---"]
        self.hedge_stake = 0.0
        self.hedge_odds = live_odds_home

        # If you have a lay liability on the selected score AND Home odds > 1
        # You can hedge by backing Home so that if Home wins, you recover the liability.
        if self.cs_liability > 0 and live_odds_home > 1.01:
            # Hedge stake to offset the liability if Home wins
            recommended_stake = self.cs_liability / (live_odds_home - 1)
            lines_hedge.append(
                f"To offset liability {self.cs_liability:.2f} on score {selected_score_str}, "
                f"consider backing Home at {live_odds_home:.2f} for stake {recommended_stake:.2f}."
            )
            lines_hedge.append(
                f"This yields a profit of {recommended_stake*(live_odds_home-1):.2f} if Home wins."
            )
            self.hedge_stake = recommended_stake
        else:
            lines_hedge.append("No hedge recommended (no liability or invalid Home odds).")

        ################################################
        # D) Scenario Outcome Table
        ################################################
        lines_scenarios = ["--- Scenario Outcome Table (Lay + Hedge) ---"]
        # We'll only incorporate:
        #   - The lay on the selected score
        #   - The recommended hedge on Home
        #
        # 1) If final score == selected => lay loses (−liability), but if Home is indeed the winner,
        #    the hedge bet wins (+hedge_stake*(odds_home−1)).
        #    (If the selected score is a Home win, we assume that's how the hedge triggers.)
        #
        # 2) If final score is a different Home win => lay bet wins (+cs_lay_stake),
        #    hedge bet also wins.
        #
        # 3) If Away wins => lay bet wins, hedge bet loses.
        #
        # 4) If Draw => lay bet wins, hedge bet loses.
        #
        # We'll just show those 4 lines for clarity.

        # Hedge bet: if Home wins => + hedge_stake*(live_odds_home - 1), else − hedge_stake
        home_win_profit = self.hedge_stake * (self.hedge_odds - 1)

        # 1) Home wins by the selected score
        #    => Lay: -cs_liability
        #    => Hedge: +home_win_profit
        scenario1_net = home_win_profit - self.cs_liability

        # 2) Home wins but NOT the selected score
        #    => Lay: +cs_lay_stake
        #    => Hedge: +home_win_profit
        scenario2_net = self.cs_lay_stake + home_win_profit

        # 3) Away wins
        #    => Lay: +cs_lay_stake
        #    => Hedge: −hedge_stake
        scenario3_net = self.cs_lay_stake - self.hedge_stake

        # 4) Draw
        #    => Lay: +cs_lay_stake
        #    => Hedge: −hedge_stake
        scenario4_net = self.cs_lay_stake - self.hedge_stake

        lines_scenarios.append(f"If Home wins by selected score: {scenario1_net:.2f}")
        lines_scenarios.append(f"If Home wins but not {selected_score_str}: {scenario2_net:.2f}")
        lines_scenarios.append(f"If Away wins: {scenario3_net:.2f}")
        lines_scenarios.append(f"If Draw: {scenario4_net:.2f}")

        ################################################
        # Combine all output lines
        ################################################
        combined_lines = []
        combined_lines.extend(lines_mo)
        combined_lines.append("")
        combined_lines.extend(lines_cs)
        combined_lines.append("")
        combined_lines.extend(lines_hedge)
        combined_lines.append("")
        combined_lines.extend(lines_scenarios)
        combined_lines.append("")

        # Display
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", tk.END)
        for line in combined_lines:
            if line.startswith("---"):
                self.output_text.insert(tk.END, line + "\n", "insight")
            elif "Lay" in line and "Recommended Lay Bet" in line:
                self.output_text.insert(tk.END, line + "\n", "lay")
            elif "Back" in line or "Hedge" in line or "offset" in line:
                self.output_text.insert(tk.END, line + "\n", "back")
            else:
                self.output_text.insert(tk.END, line + "\n", "normal")
        self.output_text.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = CombinedFootballHedgeModel(root)
    root.mainloop()
