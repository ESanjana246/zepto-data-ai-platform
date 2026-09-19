# Module 2 – Analytics & Modeling

This module performs exploratory data analysis and machine learning on the Titanic dataset.

## Contents

- `01_eda.ipynb` – Data loading, profiling, missing-value handling, outlier analysis, univariate/bivariate/multivariate analysis, correlation analysis, and standardization.
- `02_modeling.ipynb` – Classification, class-imbalance analysis, Random Forest tuning, regression, model evaluation, and deployment testing.
- `titanic.csv` – Offline copy of the Titanic dataset.
- `best_titanic_pipeline.joblib` – Saved classification pipeline for deployment.

## Classification Models

- Logistic Regression
- Decision Tree
- Random Forest
- Tuned Random Forest

## Regression Model

- Multivariate Linear Regression for fare prediction

## Best Classification Pipeline

The original Random Forest pipeline was selected based on the observed test-set F1 score and accuracy and saved using Joblib.

## Reproducibility

- Dataset loaded once and saved locally.
- Stratified train-test split used for classification.
- Preprocessing fitted only on training data.
- SMOTE applied only to the training fold.
- GridSearchCV used for Random Forest tuning.
- Complete preprocessing and model pipeline saved with Joblib.