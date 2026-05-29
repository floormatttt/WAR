import os
import pickle
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shap
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
DATASET_PATH = os.path.join(os.path.dirname(__file__), "ml_dataset.csv")

TARGETS = ["pass_epa_per_play", "pass_success_rate"]

FEATURE_SETS = {
    "Unit-Only": ["team_avg_pbwr", "team_avg_grade"],
    "Weak-Link-Only": ["team_min_pbwr", "wl_delta", "wl_snap_share", "wl_pressure_rate"],
    "Full-Model": [
        "team_avg_pbwr", "team_min_pbwr", "team_max_pbwr", "team_std_pbwr",
        "team_range_pbwr", "team_avg_grade", "team_min_grade", "team_std_grade",
        "wl_delta", "wl_snap_share", "wl_pressure_rate",
        "n_starter_qualified", "avg_cpoe",
    ],
}

TPS_FEATURE_MAP = {
    "team_avg_pbwr": "tps_avg_pbwr",
    "team_min_pbwr": "tps_min_pbwr",
    "team_max_pbwr": "tps_max_pbwr",
    "team_std_pbwr": "tps_std_pbwr",
    "team_range_pbwr": "tps_range_pbwr",
    "team_avg_grade": "tps_avg_grade",
    "team_min_grade": "tps_min_grade",
    "team_std_grade": "tps_std_grade",
    "wl_delta": "tps_wl_delta",
    "wl_snap_share": "tps_wl_snap_share",
    "wl_pressure_rate": "tps_wl_pressure_rate",
}


def tps_features(feats):
    return [TPS_FEATURE_MAP.get(f, f) for f in feats]


def loso_cv(model, X, y, seasons):
    """Leave-one-season-out cross-validation. Returns list of per-fold metrics."""
    records = []
    unique_seasons = sorted(seasons.unique())
    for season in unique_seasons:
        mask_test = seasons == season
        mask_train = ~mask_test
        X_train, X_test = X[mask_train], X[mask_test]
        y_train, y_test = y[mask_train], y[mask_test]
        m = clone_model(model)
        m.fit(X_train, y_train)
        preds = m.predict(X_test)
        records.append({
            "season": season,
            "r2": r2_score(y_test, preds),
            "mae": mean_absolute_error(y_test, preds),
            "rmse": np.sqrt(mean_squared_error(y_test, preds)),
        })
    return records


def clone_model(model):
    if isinstance(model, Pipeline):
        steps = []
        for name, step in model.steps:
            steps.append((name, type(step)(**step.get_params())))
        return Pipeline(steps)
    return type(model)(**model.get_params())


def aggregate_cv(records):
    r2s = [r["r2"] for r in records]
    maes = [r["mae"] for r in records]
    rmses = [r["rmse"] for r in records]
    return {
        "r2_mean": np.mean(r2s),
        "r2_std": np.std(r2s),
        "mae_mean": np.mean(maes),
        "rmse_mean": np.mean(rmses),
    }


def build_models():
    ridge = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=1.0)),
    ])
    xgb = XGBRegressor(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )
    return {"Ridge": ridge, "XGBoost": xgb}


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # ── Step 1: Load data ────────────────────────────────────────────────────
    print("Step 1: Loading ml_dataset.csv ...")
    df = pd.read_csv(DATASET_PATH)
    print(f"  Loaded {len(df)} rows, {len(df.columns)} columns. Seasons: {sorted(df['year'].unique())}\n")

    seasons = df["year"]
    all_rows = []

    # ── Step 2: Cross-validation ─────────────────────────────────────────────
    print("Step 2: Running Leave-One-Season-Out cross-validation ...")

    for target in TARGETS:
        y = df[target]
        for fs_name, feats in FEATURE_SETS.items():
            for tps in [False, True]:
                cols = tps_features(feats) if tps else feats
                missing = [c for c in cols if c not in df.columns]
                if missing:
                    print(f"  [SKIP] {fs_name} TPS={tps} - missing columns: {missing}")
                    continue
                X = df[cols].values
                models = build_models()
                for algo_name, model in models.items():
                    tag = f"{algo_name} | {fs_name} | TPS={'Yes' if tps else 'No'} | {target}"
                    print(f"  Training {tag} ...")
                    records = loso_cv(model, X, y, seasons)
                    agg = aggregate_cv(records)
                    all_rows.append({
                        "Algorithm": algo_name,
                        "Feature Set": fs_name,
                        "TPS": "Yes" if tps else "No",
                        "Target": target,
                        "OOS R²": round(agg["r2_mean"], 4),
                        "R² Std": round(agg["r2_std"], 4),
                        "MAE": round(agg["mae_mean"], 5),
                        "RMSE": round(agg["rmse_mean"], 5),
                    })

    results_df = pd.DataFrame(all_rows)

    # Print Markdown table
    print("\n\n## Cross-Validation Results\n")
    cols_show = ["Algorithm", "Feature Set", "TPS", "Target", "OOS R²", "MAE"]
    sub = results_df[cols_show].copy()
    sub = sub.sort_values(["Target", "OOS R²"], ascending=[True, False])

    # Build markdown table
    header = "| " + " | ".join(cols_show) + " |"
    sep = "| " + " | ".join(["---"] * len(cols_show)) + " |"
    rows = []
    for _, row in sub.iterrows():
        rows.append("| " + " | ".join(str(row[c]) for c in cols_show) + " |")
    print(header)
    print(sep)
    print("\n".join(rows))

    # ── Step 3: SHAP analysis ────────────────────────────────────────────────
    print("\n\nStep 3: Training final XGBoost Full-Model on entire dataset for SHAP ...")
    full_feats = FEATURE_SETS["Full-Model"]
    X_full = df[full_feats].values
    y_full = df["pass_epa_per_play"].values

    final_xgb = XGBRegressor(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )
    final_xgb.fit(X_full, y_full)

    print("  Computing SHAP values ...")
    explainer = shap.TreeExplainer(final_xgb)
    shap_values = explainer.shap_values(X_full)

    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    importance_df = pd.DataFrame({
        "feature": full_feats,
        "mean_abs_shap": mean_abs_shap,
    }).sort_values("mean_abs_shap", ascending=False)

    # Save SHAP summary plot
    shap_png = os.path.join(RESULTS_DIR, "shap_summary.png")
    shap.summary_plot(shap_values, X_full, feature_names=full_feats, show=False)
    plt.tight_layout()
    plt.savefig(shap_png, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved SHAP summary plot -> {shap_png}")

    # Save feature importances text
    fi_path = os.path.join(RESULTS_DIR, "feature_importances.txt")
    with open(fi_path, "w") as f:
        f.write("Feature Importances (mean |SHAP|) -- Full-Model XGBoost -> pass_epa_per_play\n")
        f.write("=" * 65 + "\n")
        for _, r in importance_df.iterrows():
            f.write(f"{r['feature']:<30}  {r['mean_abs_shap']:.6f}\n")
    print(f"  Saved feature importances ->{fi_path}")

    # ── Step 4: Save outputs ─────────────────────────────────────────────────
    print("\nStep 4: Saving outputs ...")

    csv_path = os.path.join(RESULTS_DIR, "model_comparison.csv")
    results_df.to_csv(csv_path, index=False)
    print(f"  Saved model comparison CSV ->{csv_path}")

    # Train final Ridge and XGBoost Full-Models on all data for pickling
    final_ridge = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=1.0)),
    ])
    final_ridge.fit(X_full, y_full)

    ridge_pkl = os.path.join(RESULTS_DIR, "ridge_full_model.pkl")
    xgb_pkl = os.path.join(RESULTS_DIR, "xgboost_full_model.pkl")
    with open(ridge_pkl, "wb") as f:
        pickle.dump(final_ridge, f)
    with open(xgb_pkl, "wb") as f:
        pickle.dump(final_xgb, f)
    print(f"  Saved Ridge model ->{ridge_pkl}")
    print(f"  Saved XGBoost model ->{xgb_pkl}")

    print("\nDone.")


if __name__ == "__main__":
    main()

#a