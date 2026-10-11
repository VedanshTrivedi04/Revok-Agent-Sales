# Expansion opportunity - report

Source: **synthetic**. Rows: 20859, positive rate 0.1768.

| Model (test, newest data) | AUC-ROC | AUC-PR | Brier | ECE | Top-10% precision | Top-10% lift |
|---|---|---|---|---|---|---|
| LightGBM + calibration | 0.7806 | 0.5003 | 0.1129 | 0.0119 | 0.5773 | 3.41 |
| Logistic regression | 0.7715 | 0.4713 | 0.1159 | 0.0123 | 0.567 | 3.35 |
| Rules baseline | 0.6847 | 0.3343 | - | - | 0.4914 | 2.9 |

95% bootstrap CI (LightGBM): {'auc_roc': [0.7567, 0.8016], 'auc_pr': [0.4533, 0.5427], 'brier': [0.1055, 0.1211]}

Release gates: {'ece_below_0.05': True, 'beats_rules_baseline': True, 'production_ready': False, 'reason_not_ready': 'trained on SYNTHETIC data'}

Plots: shap_summary.png, shap_importance.png, waterfall_highest_risk.png, waterfall_lowest_risk.png, dependence_seat_util.png, dependence_usage_change_pct.png, dependence_upgrade_intent_30d.png, calibration.png
