from anki_client import AnkiClient
from gui import FlashcardGUI


MODEL_NAME = "*L2: 2025 Revamp"


def main():
    client = AnkiClient()

    try:
        decks = client.deck_names()
    except Exception as e:
        raise SystemExit(
            f"Could not connect to AnkiConnect. Make sure Anki is running.\n{e}"
        )

    def on_add(deck: str, word: str, meaning: str):
        fields = {"Front": word, "Back": meaning}
        try:
            added = client.add_note(deck, MODEL_NAME, fields)
            if not added:
                return False, "Note already exists (duplicate)"
            return True, ""
        except Exception as exc:
            return False, str(exc)

    gui = FlashcardGUI(decks, on_add)
    gui.mainloop()


if __name__ == "__main__":
    main()