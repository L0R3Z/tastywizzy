# Paramètres de config.json

Référence de chaque réglage. Ce fichier sert de source pour les infobulles de l'interface (V2). Version anglaise : [PARAMETERS.md](PARAMETERS.md).

**Format de chaque entrée** (pensé pour être lu par un script) :
- le titre `### clé` est la clé exacte de `config.json` ;
- **Libellé** : nom court affiché dans l'interface ;
- **Infobulle** : texte court (une ou deux phrases) à afficher au survol ;
- **Type / Défaut / Plage** : type de contrôle à prévoir dans l'interface ;
- **Prise en compte** : « à chaud » (appliqué dès l'enregistrement) ou « au redémarrage » ;
- **Détails** : explication longue, pour un lien « en savoir plus ».

Les défauts indiqués sont ceux du code (`src/lights/config.py`). Le `config.json` actuel peut en différer.

---

## Ampoules et capture

### bulbs
- **Libellé** : Ampoules
- **Infobulle** : Noms et adresses IP des ampoules WiZ à piloter. Toutes reçoivent la même couleur.
- **Type** : dictionnaire nom → adresse IP, ou nom → `{"ip": ..., "mac": ...}`
- **Défaut** : `{"plafonnier": "192.168.1.101", "bureau": "192.168.1.102"}`
- **Prise en compte** : au redémarrage
- **Détails** : les IP sont réservées sur la SFR Box (réservation DHCP : plafonnier .101, bureau .102). Au lancement, l'appli lit l'adresse MAC de chaque ampoule et l'enregistre ici automatiquement ; si une ampoule ne répond plus à son IP, elle est recherchée par MAC sur le réseau local et `config.json` est corrigé tout seul. Une ampoule introuvable est ignorée et recherchée de nouveau toutes les `bulb_retry_s` secondes.

### bulb_retry_s
- **Libellé** : Délai de nouvelle recherche
- **Infobulle** : Toutes les combien de secondes l'appli recherche une ampoule injoignable.
- **Type** : nombre (secondes)
- **Défaut** : `30`
- **Prise en compte** : au redémarrage
- **Détails** : la recherche se fait en arrière-plan, sans ralentir la synchro des autres ampoules.

### monitor
- **Libellé** : Écran capturé
- **Infobulle** : « primary » capture l'écran principal, « all » capture tous les écrans ensemble.
- **Type** : choix (`primary` ou `all`)
- **Défaut** : `primary`
- **Prise en compte** : au redémarrage
- **Détails** : avec `all`, les écrans sont fusionnés en une seule image (bureau virtuel), et la couleur est la moyenne de tous.

### crop_black_bars
- **Libellé** : Ignorer les bandes noires
- **Infobulle** : Détecte et ignore les bandes noires autour de l'image (films en 21:9, etc.) pour ne pas assombrir la moyenne.
- **Type** : booléen
- **Défaut** : `true`
- **Prise en compte** : à chaud
- **Détails** : la détection est automatique, sur les bords de l'image. Si tout l'écran est noir, l'image est gardée telle quelle. La barre des tâches n'est pas gérée séparément (elle est masquée sur ce poste).

### capture_hz
- **Libellé** : Fréquence de capture
- **Infobulle** : Nombre de captures d'écran par seconde. Plus c'est haut, plus la réaction est vive, mais plus le processeur travaille.
- **Type** : nombre (Hz)
- **Défaut** : `30`
- **Plage conseillée** : 10 à 60
- **Prise en compte** : à chaud
- **Détails** : indépendant de `send_hz`. Il n'est pas utile que la capture soit beaucoup plus rapide que l'envoi.

---

## Envoi aux ampoules et lissage

### send_hz
- **Libellé** : Envois par seconde
- **Infobulle** : Nombre maximal de commandes envoyées aux ampoules par seconde. Plus c'est haut, plus c'est fluide, mais les ampoules lentes peuvent prendre du retard.
- **Type** : nombre (Hz)
- **Défaut** : `10`
- **Plage conseillée** : 2 à 10 (2 est saccadé, 5 est fluide, 10 est plus fluide encore)
- **Prise en compte** : à chaud
- **Détails** : l'envoi est en UDP, sans attendre de réponse. La lampe de bureau répond lentement (jusqu'à 1 s) et peut être en retard sur le plafonnier.

### tau
- **Libellé** : Lissage (τ)
- **Infobulle** : Durée du lissage des changements de couleur, en secondes. Petit = réactif mais nerveux, grand = doux mais en retard.
- **Type** : nombre (secondes)
- **Défaut** : `0.1`
- **Plage conseillée** : 0 à 1 (0 désactive le lissage)
- **Prise en compte** : à chaud
- **Détails** : s'ajoute au fondu interne des ampoules (environ 0,5 à 1 s). La teinte lissée prend toujours le chemin le plus court sur le cercle des couleurs.

### min_change
- **Libellé** : Seuil de changement
- **Infobulle** : Écart minimal de couleur ou de luminosité pour envoyer une nouvelle commande. Évite d'inonder les ampoules pour des variations invisibles.
- **Type** : nombre entier (échelle 0 à 255 pour les couleurs, 0 à 100 pour la luminosité)
- **Défaut** : `2`
- **Plage conseillée** : 0 à 10
- **Prise en compte** : à chaud
- **Détails** : la comparaison prend le plus grand écart parmi rouge, vert, bleu et luminosité. Un seuil trop haut donne des paliers visibles.

---

## Couleurs neutres (noir, gris, blanc)

### neutral_low
- **Libellé** : Seuil « image neutre »
- **Infobulle** : Sous ce niveau de couleur dans l'image, les ampoules prennent la couleur neutre au lieu de la teinte moyenne.
- **Type** : nombre
- **Défaut** : `0.06`
- **Plage conseillée** : 0 à 0.3 (doit rester inférieur à `neutral_high`)
- **Prise en compte** : à chaud
- **Détails** : le niveau de couleur est la moyenne de saturation × luminosité des pixels. Plus la valeur est haute, plus d'images sombres ou désaturées sont traitées comme neutres, ce qui évite les dominantes parasites (par exemple une teinte bleue ou rose sur une scène grise).

### neutral_high
- **Libellé** : Seuil « couleur pleine »
- **Infobulle** : À partir de ce niveau de couleur, les ampoules prennent pleinement la teinte moyenne de l'écran.
- **Type** : nombre
- **Défaut** : `0.14`
- **Plage conseillée** : 0.05 à 0.5 (doit rester supérieur à `neutral_low`)
- **Prise en compte** : à chaud
- **Détails** : entre `neutral_low` et `neutral_high`, la couleur neutre et la teinte moyenne sont mélangées progressivement.

### neutral_rgb
- **Libellé** : Couleur neutre
- **Infobulle** : Couleur utilisée quand l'image est noire, grise ou blanche. Choisis un blanc chaud ou un blanc pur.
- **Type** : couleur (3 valeurs rouge, vert, bleu de 0 à 255)
- **Défaut** : `[255, 255, 255]`
- **Prise en compte** : à chaud
- **Détails** : un blanc pur peut paraître bleuté ou rosé selon l'ampoule. Un blanc chaud (par exemple `[255, 200, 130]`) est souvent plus agréable. Les ampoules fabriquent ce blanc avec leurs LED de couleur, d'où des écarts de teinte possibles.

### use_white_led
- **Libellé** : Utiliser la LED blanche
- **Infobulle** : Activé : les images neutres sont rendues par la LED blanche chaude de l'ampoule. Désactivé : tout est fait avec les LED RGB.
- **Type** : booléen
- **Défaut** : `false`
- **Prise en compte** : à chaud
- **Détails** : activé, la LED blanche chaude (canal `w`) remplace la couleur neutre, et `neutral_rgb` n'est plus utilisé. Entre image neutre et colorée, les LED RGB et la LED blanche sont mélangées progressivement. Nécessite une ampoule WiZ RGBW (couleur + blanc).

---

## Luminosité

### dynamic_brightness
- **Libellé** : Luminosité dynamique
- **Infobulle** : Activé : la luminosité suit l'écran. Désactivé : luminosité fixe (voir « Luminosité fixe »).
- **Type** : booléen
- **Défaut** : `true`
- **Prise en compte** : à chaud
- **Détails** : désactivé, seuls la couleur et la teinte suivent l'écran. Les réglages de mode jour/nuit, de gamma, de gain et de plafonds ne s'appliquent plus.

### fixed_brightness
- **Libellé** : Luminosité fixe
- **Infobulle** : Luminosité utilisée quand la luminosité dynamique est désactivée, en pourcentage.
- **Type** : curseur (%)
- **Défaut** : `80`
- **Plage** : 10 à 100 (10 est le minimum des ampoules WiZ)
- **Prise en compte** : à chaud
- **Détails** : sans effet tant que `dynamic_brightness` est activé.

### brightness_mode
- **Libellé** : Mode jour / nuit
- **Infobulle** : « night » est plus tamisé, « day » plus lumineux. Bascule entre deux profils de luminosité.
- **Type** : choix (`night` ou `day`)
- **Défaut** : `night`
- **Prise en compte** : à chaud
- **Détails** : le mode choisit à la fois le minimum (`dimming_min_by_mode`) et le coefficient global (`brightness_scales`). Une clé de mode absente de ces deux réglages invalide la configuration.

### brightness_scales
- **Libellé** : Coefficient global par mode
- **Infobulle** : Multiplie toute la luminosité dynamique. 0,8 réduit de 20 %, 1 laisse tel quel.
- **Type** : dictionnaire mode → nombre
- **Défaut** : `{"night": 0.8, "day": 1.0}`
- **Plage conseillée** : 0.1 à 1 par mode
- **Prise en compte** : à chaud
- **Détails** : s'applique avant le minimum, qui reste toujours respecté. Sans effet si la luminosité dynamique est désactivée.

### dimming_min_by_mode
- **Libellé** : Luminosité minimale par mode
- **Infobulle** : Luminosité plancher des ampoules, par mode, en pourcentage. C'est le niveau atteint sur un écran tout noir.
- **Type** : dictionnaire mode → pourcentage
- **Défaut** : `{"night": 10, "day": 25}`
- **Plage** : 10 à 100 par mode (10 est le minimum matériel des ampoules WiZ)
- **Prise en compte** : à chaud
- **Détails** : un minimum plus haut en mode jour garde la pièce éclairée même sur une scène noire. Sans effet si la luminosité dynamique est désactivée.

### dimming_max
- **Libellé** : Luminosité maximale (couleurs)
- **Infobulle** : Plafond de luminosité pour les scènes colorées, en pourcentage.
- **Type** : curseur (%)
- **Défaut** : `100`
- **Plage** : 10 à 100
- **Prise en compte** : à chaud
- **Détails** : plafond général. Avec `use_white_led`, il s'applique aux images colorées et le plafond passe progressivement de `dimming_max_white` (image neutre) à `dimming_max` (image colorée). Sans `use_white_led`, il s'applique à toutes les images.

### dimming_max_white
- **Libellé** : Luminosité maximale (blancs)
- **Infobulle** : Plafond de luminosité pour les scènes blanches ou grises, en pourcentage. Les blancs éblouissent plus que les couleurs.
- **Type** : curseur (%)
- **Défaut** : `60`
- **Plage** : 10 à 100
- **Prise en compte** : à chaud
- **Détails** : à même pourcentage, un blanc paraît bien plus lumineux qu'une couleur, car il allume toutes les LED. Baisser ce plafond adoucit les scènes claires et les menus blancs. Le monter donne plus d'amplitude sur les écrans neutres. Utilisé seulement si `use_white_led` est activé.

### brightness_gain
- **Libellé** : Gain de luminosité
- **Infobulle** : Amplifie la luminosité mesurée sur l'écran. Plus c'est haut, plus les ampoules montent vite, même sur des scènes plutôt sombres.
- **Type** : nombre
- **Défaut** : `2.0`
- **Plage conseillée** : 1 à 4
- **Prise en compte** : à chaud
- **Détails** : la luminosité moyenne d'une scène typique est faible (souvent autour de 0,3), d'où un gain supérieur à 1. Un gain trop haut sature vite au plafond. Sans effet si la luminosité dynamique est désactivée.

### brightness_gamma
- **Libellé** : Courbe de luminosité
- **Infobulle** : Au-dessus de 1, les scènes sombres restent bien sombres. En dessous de 1, elles s'éclaircissent plus vite.
- **Type** : nombre
- **Défaut** : `1.5`
- **Plage conseillée** : 0.5 à 3
- **Prise en compte** : à chaud
- **Détails** : 1 donne une réponse linéaire. Utile pour éviter qu'une petite zone claire sur fond sombre (par exemple du texte sur une barre grise) fasse monter fortement les ampoules. Sans effet si la luminosité dynamique est désactivée.

---

## Pause et arrêt

### pause_hotkey
- **Libellé** : Raccourci de pause
- **Infobulle** : Raccourci clavier global qui met la synchro en pause et la reprend, même depuis un jeu.
- **Type** : raccourci clavier (chaîne)
- **Défaut** : `ctrl+alt+l`
- **Prise en compte** : au redémarrage
- **Détails** : modificateurs possibles : `ctrl`, `alt`, `shift`, `win`, suivis d'une lettre, d'un chiffre ou d'une touche `f1` à `f24` (exemple : `ctrl+shift+f9`). Une chaîne vide désactive le raccourci. Si la combinaison est déjà utilisée par un autre programme, un avertissement s'affiche au démarrage et la pause par raccourci n'est pas disponible.

### pause_mode
- **Libellé** : Comportement de la pause
- **Infobulle** : « restore » remet les ampoules dans leur état d'origine pendant la pause. « freeze » garde la dernière couleur.
- **Type** : choix (`restore` ou `freeze`)
- **Défaut** : `restore`
- **Prise en compte** : à chaud
- **Détails** : en `restore`, l'état restauré est celui sauvegardé au lancement du programme. À la reprise, la synchro repart de zéro, sans lissage hérité.

### auto_pause_session
- **Libellé** : Pause au verrouillage et à la veille
- **Infobulle** : Met la synchro en pause et remet les ampoules dans leur état d'origine quand la session est verrouillée (Win+L) ou que le PC part en veille. Reprise automatique au déverrouillage.
- **Type** : booléen
- **Défaut** : `true`
- **Prise en compte** : à chaud
- **Détails** : l'état d'origine est toujours restauré, quel que soit `pause_mode`. Une pause manuelle (raccourci ou icône) reste active après le déverrouillage. À la mise en veille, la restauration est envoyée immédiatement, avant la coupure du réseau.

### restore_on_exit
- **Libellé** : Restaurer à la fermeture
- **Infobulle** : À la fermeture du programme (fenêtre fermée, Ctrl+C, arrêt de Windows), remet les ampoules dans leur état d'origine.
- **Type** : booléen
- **Défaut** : `true`
- **Prise en compte** : à chaud
- **Détails** : l'état d'origine (scène, température, luminosité, allumage) est lu avec `getPilot` au lancement. Si une ampoule ne répond pas à ce moment-là, elle n'est pas restaurée. La commande est envoyée deux fois par sécurité, l'envoi UDP n'ayant pas d'accusé de réception. Désactivé, les ampoules gardent leur dernière couleur.
