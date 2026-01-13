# 🏃‍♂️ Trail Performance Analytics
### Prédiction de l’allure à partir des données Strava

## 🎯 Objectif
Ce projet vise à prédire l’allure moyenne (en secondes par kilomètre) d’une sortie de course à partir des données Strava, en s’appuyant uniquement sur la charge d’entraînement récente et le profil terrain.

Il répond à une question concrète de coaching sportif :
> *À quelle allure puis-je raisonnablement courir aujourd’hui, compte tenu de mon entraînement récent ?*

---

## 📊 Données
- Données issues de l’API Strava
- Activités agrégées (distance, durée, dénivelé)
- Fenêtres glissantes de charge (7 jours / 28 jours)

Les données physiologiques (fréquence cardiaque, puissance) ne sont pas encore intégrées.

---

## 🏗️ Pipeline data
- Authentification OAuth Strava
- Ingestion automatisée via GitHub Actions
- Stockage PostgreSQL
- Feature engineering orienté charge externe
- Modélisation avec split temporel

---

## 🤖 Modélisation
- **Target** : allure moyenne (sec/km)
- **Baseline** : allure moyenne historique
- **Modèle** : Random Forest Regressor
- **Évaluation** : split temporel (80 % passé / 20 % récent)

### Résultats
- **MAE ≈ 36 secondes/km**
- Amélioration d’environ 40 % par rapport à la baseline

Ces résultats montrent que la charge récente et le dénivelé expliquent une part significative de la performance, même sans données cardio.

---

## 🔍 Enseignements clés
- La charge sur 7 jours est plus prédictive que le volume long terme
- Le profil terrain influence fortement l’allure
- Un modèle simple peut déjà fournir des insights utiles au coaching

---

## 🚀 Perspectives
- Ajout des streams Strava (fréquence cardiaque, puissance)
- Prédiction du temps total de course
- Analyse multi-athlètes
- Outil d’aide au coaching personnalisé

---

## 🔐 Confidentialité
Les données sont privées, utilisées uniquement avec le consentement explicite des athlètes, et peuvent être révoquées à tout moment.

---

## 👤 Auteur
**Orlane Houzet**  
Data Scientist – Marketing & Performance Analytics
