from tinydb import TinyDB, Query

# Dati dei tag da inserire
tags_data = {
    "Preferiti": "⭐",
    "Da leggere": "📖",
    "Filosofia": "🤔",
    "Teologia": "✝️",
    "Morale": "⚖️",
    "Spiritualità": "🕊️",
    "Storia": "🏛️",
    "Esegesi": "📜",
    "Sacramenti": "💧",
    "Liturgia": "🕯️",
    "Pastorale": "🐑",
    "Domenicani": "⚪⚫",
    "Tommaso d'Aquino": "😇",
    "STh-Salani": "📚",
    "Questioni Disputate": "❓",
    "Manuali": "📘",
    "Enciclopedie & Dizionari": "📖",
    "Padri della Chiesa": "📜",
    "Scienza": "🔬",
    "Tecnologia": "💻",
    "Tecnoetica": "💡",
    "Post-Trans-Umanesimo": "🤖",
    "Pop philosophy": "🎬",
    "Letteratura": "✒️",
    "Religioni": "🕉️",
    "Linguistica": "🗣️",
    "Bioetica": "🧬",
    "Sociologia": "👥",
    "Diritto": "⚖️",
    "Logica": "🧠",
    "default": "📄"
}

# Connessione al database TinyDB
db = TinyDB('test_library.json')  # Sostituisci con il percorso del tuo database
tags_table = db.table('tags')

# Inserimento dei tag
for name, icon in tags_data.items():
    # Verifica se il tag esiste già
    Tag = Query()
    existing_tag = tags_table.get(Tag.name == name)
    
    if existing_tag:
        # Aggiorna il tag esistente
        tags_table.update({'icon': icon}, Tag.name == name)
        print(f"Tag '{name}' aggiornato con icona '{icon}'")
    else:
        # Inserisce un nuovo tag
        tags_table.insert({'name': name, 'icon': icon})
        print(f"Tag '{name}' aggiunto con icona '{icon}'")

print("Operazione completata!")