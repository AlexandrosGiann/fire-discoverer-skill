# fire-discoverer

Skill για Claude Code: σιωπηλή δουλειά, σύντομες ειδοποιήσεις, έλεγχος σπάνιων σεναρίων, πολύ σύντομο τελικό αποτέλεσμα.

**Δεν είναι φθηνότερο από το Caveman.** Στις μετρήσεις έκαψε 24% περισσότερα output tokens και κόστισε 27% περισσότερο. Σε αντάλλαγμα πέρασε 81/84 κρυφούς ελέγχους έναντι 78/84, και έδωσε λίγο πιο σύντομες τελικές απαντήσεις. Λεπτομέρειες στο [benchmark/RESULTS.md](benchmark/RESULTS.md).

## Κανόνες

- Κανόνες Caveman, ενσωματωμένοι ώστε να μη φορτώνονται δύο skills.
- Καμία ειδοποίηση όταν διαβάζει.
- Μία γραμμή όταν κατεβάζει ή γράφει. Σε ολοκαίνουργιο project, μόνο όταν κατεβάζει.
- Ελέγχει και λιγότερο πιθανά σενάρια.
- Τελικό αποτέλεσμα έως 5 γραμμές.
- Τοπικά μοντέλα μόνο όπου πέρασαν τις δοκιμές: Whistle, MobileCLIP και MiniLM, με περιορισμούς. Όχι SmolLM2 και Needle.

## Εγκατάσταση

```bash
git clone https://github.com/AlexandrosGiann/fire-discoverer-skill ~/.claude/skills/fire-discoverer
```

Προαιρετικά, για τα τοπικά μοντέλα (χρειάζεται git, curl, cargo· κατεβάζει περίπου 390 MB):

```bash
sh ~/.claude/skills/fire-discoverer/scripts/setup-models.sh
```

Ενεργοποίηση με `/fire-discoverer`, απενεργοποίηση με `stop fire-discoverer` ή `normal mode`.
