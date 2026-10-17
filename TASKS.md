# Tasks

## Active

## Waiting On

## Someday
- [ ] **Réservation DHCP des ampoules sur le routeur** - IP fixes actuelles : 192.168.1.29 / .33
- [ ] **V2 : appli tray + interface de réglages** - luminosité suit l'écran (min/max), raccourci pause (restaurer par défaut / figer en option), auto-pause verrouillage/veille/inactivité, profils Film/Jeu/Travail, pystray, PyInstaller
- [ ] **Zones d'écran par ampoule** - option activable
- [ ] **Bascule blanc chaud si faible saturation** - option activable
- [ ] **Capture dxcam** - pour jeux plein écran exclusif
- [ ] **Réaction audio (WASAPI loopback)** - après que la synchro de teinte soit terminée

## Done
- [x] **Trouver les IP des 2 ampoules** - plafonnier 192.168.1.29, bureau 192.168.1.33 (répondent en UDP)
- [x] **Installer Python 3.12+** - Python 3.12.10 installé via winget (rouvrir le terminal pour le PATH)
- [x] **Tester le fondu interne des ampoules WiZ** - fondu natif ~0,5-1 s ; 2 Hz saccadé, 5 Hz fluide, 10 Hz plus fluide ; bureau parfois en retard (RTT ~400 ms vs ~140 ms) ; saut de teinte bleu/vert sur les deux ampoules (limite RGB). Cadence configurable, défaut 5 Hz
- [x] **V1 : script de synchro écran → WiZ** - package `src/lights/` (config, capture, color, smoothing, wiz, app) + main.py + requirements.txt (mss, numpy). Écran principal par défaut, option les deux écrans. Recadrage auto-détecté des bords/bandes noires (ON par défaut, désactivable, pas de marge fixe). Moyenne circulaire de teinte, lissage temporel (τ ~0,4 s), UDP ~5 Hz sans attente de réponse, seuil de changement
- [x] **Retours test V1** - fluide ; léger retard (τ/cadence réglables) ; bleu parasite sur images sombres/grises -> seuil de neutralité + blanc chaud ; figé sur écran noir -> luminosité suivant l écran (min/max, gain). Tous ces paramètres dans config.json, à exposer dans l UI V2. Retours : RGB (sans mode temp) = plus de bleu sur rouge->noir, noir au minimum, délai acceptable (τ 0,1 s, 10 Hz), luminosité jour/nuit OK. Reste : choisir le blanc neutre (neutral_rgb) – blanc pur bleuté/rosé, test d un blanc chaud en cours. Restent : léger retard (fondu natif des ampoules), passage par le bleu entre couleur et blanc à surveiller
- [x] **Sauvegarde/restauration de l'état des ampoules** - getPilot au lancement, restauration à l'arrêt par défaut, option désactivable
- [x] **Raccourci global de pause** - Ctrl+Alt+L (pause_hotkey), mode restore (état d origine) ou freeze (pause_mode) ; codé, à valider en session gaming
