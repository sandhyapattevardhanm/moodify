# model.py
import pandas as pd
import pickle
import os

from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, classification_report
)

# === 1. Load Dataset ===
df = pd.read_csv('data/SingerAndSongs.csv')

# === 2. Create 'target' column (1 = Sad, 0 = Happy) ===
def determine_target(row):
    if row['valence'] <= 0.5 or row['energy'] <= 0.5 or row['tempo'] <= 90:
        return 1  # Sad
    else:
        return 0  # Happy

df['target'] = df.apply(determine_target, axis=1)
df.to_csv('data/sad2.csv', index=False)
print("[✔] Saved labeled dataset to data/sad2.csv")

# === 3. Select Features ===
X = df[['energy', 'valence', 'tempo']]
y = df['target']

# === 4. Train/Test Split ===
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# === 5. Train Model ===
model = KNeighborsClassifier(n_neighbors=5)
model.fit(X_train, y_train)

# === 6. Evaluate Model ===
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)

print("\n=== Model Evaluation ===")
print(f"Accuracy : {accuracy:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall   : {recall:.4f}")
print(f"F1 Score : {f1:.4f}")
print("\nClassification Report:\n", classification_report(y_test, y_pred))

# === 7. Save Model ===
with open('KNN_Model.pkl', 'wb') as f:
    pickle.dump(model, f)

print("[✔] Model saved to KNN_Model.pkl")
