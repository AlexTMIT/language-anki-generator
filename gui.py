import tkinter as tk
from tkinter import messagebox, ttk


class FlashcardGUI(tk.Tk):
    def __init__(self, deck_names: list[str], on_add):
        super().__init__()
        self.title("L2 Flashcard Generator")

        # callback provided by main app
        self._on_add = on_add

        # ---- widgets ----------------------------------------------------
        # Deck selector
        ttk.Label(self, text="Deck:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.deck_var = tk.StringVar(value=deck_names[0] if deck_names else "")
        self.deck_cb = ttk.Combobox(self, textvariable=self.deck_var, values=deck_names)
        self.deck_cb.grid(row=0, column=1, sticky="we", padx=4, pady=4)

        # Word field
        ttk.Label(self, text="Word:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.word_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.word_var).grid(
            row=1, column=1, sticky="we", padx=4, pady=4
        )

        # Meaning field
        ttk.Label(self, text="Meaning:").grid(
            row=2, column=0, sticky="e", padx=4, pady=4
        )
        self.meaning_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.meaning_var).grid(
            row=2, column=1, sticky="we", padx=4, pady=4
        )

        # Add button
        ttk.Button(self, text="Add Card", command=self._handle_add).grid(
            row=3, column=0, columnspan=2, pady=8
        )

        # Status label
        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, foreground="blue").grid(
            row=4, column=0, columnspan=2
        )

        # nice resizing
        self.columnconfigure(1, weight=1)

    # ---------------------------------------------------------------------
    def _handle_add(self):
        deck = self.deck_var.get().strip()
        word = self.word_var.get().strip()
        meaning = self.meaning_var.get().strip()

        if not (deck and word and meaning):
            messagebox.showwarning(
                "Missing info", "Please fill deck, word *and* meaning."
            )
            return

        ok, msg = self._on_add(deck, word, meaning)  # call into main app
        if ok:
            self.status_var.set(f"✓ Added “{word}” to {deck}")
            self.word_var.set("")
            self.meaning_var.set("")
        else:
            messagebox.showerror("Error", msg)