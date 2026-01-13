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

---

## 🧱 Architecture & choix techniques

### Objectif
Construire un pipeline data complet (ingestion → features → modélisation → visualisation) à partir des données Strava, avec une approche reproductible et proche de contraintes réelles de production.

### Stack technique
- **Strava API (OAuth)** : accès aux données d’activités avec consentement explicite des athlètes
- **PostgreSQL (Supabase)** : stockage structuré, historisation et support du multi-athlètes
- **Python** : ingestion, feature engineering et modélisation
- **GitHub Actions (cron)** : automatisation quotidienne de l’ingestion
- **Streamlit** : interface utilisateur pour la connexion Strava et la visualisation des résultats

### Choix de PostgreSQL
PostgreSQL permet :
- de centraliser les données dans un schéma structuré
- de calculer des features analytiques directement en SQL (fenêtres glissantes 7j / 28j)
- de gérer facilement plusieurs athlètes via des clés `athlete_id`

### Sécurité et confidentialité
- Les secrets (tokens, credentials) ne sont jamais versionnés
- Gestion via GitHub Secrets et Streamlit Secrets
- Les athlètes peuvent révoquer l’accès à tout moment depuis Strava

### Choix de modélisation
- **Target** : allure moyenne (secondes par kilomètre)
- **Validation** : split temporel (80 % passé / 20 % récent) pour éviter toute fuite de données
- **Baseline** : allure moyenne historique
- **Modèle** : Random Forest Regressor pour capturer les relations non linéaires

### Résultats
Le modèle atteint une **erreur moyenne d’environ 36 secondes par kilomètre**, en utilisant uniquement des variables de charge externe et de terrain, sans données physiologiques (HR / puissance).

### Limites et perspectives
- Données physiologiques non encore intégrées
- Prochaine étape : ingestion des streams Strava (fréquence cardiaque, puissance, altitude) pour enrichir l’analyse et améliorer la prédiction

---

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
