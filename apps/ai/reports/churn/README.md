# Churn / downgrade risk - report

Source: **synthetic**. Rows: 20859, positive rate 0.1455.

| Model (test, newest data) | AUC-ROC | AUC-PR | Brier | ECE | Top-10% precision | Top-10% lift |
|---|---|---|---|---|---|---|
| LightGBM + calibration | 0.8359 | 0.5524 | 0.0824 | 0.0193 | 0.5773 | 4.41 |
| Logistic regression | 0.832 | 0.545 | 0.0834 | 0.0146 | 0.5911 | 4.51 |
| Rules baseline | 0.752 | 0.4122 | - | - | 0.4433 | 3.39 |

95% bootstrap CI (LightGBM): {'auc_roc': [0.8098, 0.8605], 'auc_pr': [0.4983, 0.6052], 'brier': [0.0758, 0.09]}

Release gates: {'ece_below_0.05': True, 'beats_rules_baseline': True, 'production_ready': False, 'reason_not_ready': 'trained on SYNTHETIC data'}

Plots: shap_summary.png, shap_importance.png, waterfall_highest_risk.png, waterfall_lowest_risk.png, dependence_champion_changed.png, dependence_days_since_meeting.png, dependence_seat_util.png, calibration.png
