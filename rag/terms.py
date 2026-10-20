"""Arabic Islamic terms -> English expansions (F12 query expansion) and short glossary entries (F19).

Definitions are short, self-written, general-reference glosses. Noor's glossary command pairs each
one with passages from the library, so the reader sees how their own books use the term.
"""
from __future__ import annotations

import re

from rag.store import fold

# term: (spellings, English search words, one-line gloss)
TERMS: dict[str, tuple[list[str], str, str]] = {
    "sabr": (["sabr", "saber"], "patience perseverance endurance steadfastness",
             "Patience: holding steady through hardship, in obedience and in avoiding wrong."),
    "shukr": (["shukr", "shukur"], "gratitude thankfulness thanks",
              "Gratitude: recognising a blessing, thanking God for it and using it well."),
    "tawakkul": (["tawakkul", "tawakul"], "trust reliance relying on God",
                 "Reliance on God: taking the means while trusting God with the outcome."),
    "tawbah": (["tawbah", "tawba", "tauba"], "repentance repent turning back forgiveness",
               "Repentance: turning back to God with regret and a resolve not to return to the sin."),
    "taqwa": (["taqwa", "taqwah"], "God-consciousness piety fear of God mindful righteousness",
              "God-consciousness: guarding oneself by keeping God in mind in every act."),
    "ikhlas": (["ikhlas", "ikhlaas"], "sincerity sincere purity of intention",
               "Sincerity: doing a deed for God alone, not for praise."),
    "niyyah": (["niyyah", "niyya", "niyah"], "intention intentions",
               "Intention: the purpose in the heart behind an action."),
    "ihsan": (["ihsan", "ihsaan"], "excellence worship as though you see Him doing good",
              "Excellence: worshipping God as though you see Him, and doing things beautifully."),
    "iman": (["iman", "imaan", "eman"], "faith belief believe",
             "Faith: belief in God, His angels, books, messengers, the Last Day and destiny."),
    "tawhid": (["tawhid", "tawheed", "tauhid"], "oneness of God monotheism unity",
               "The oneness of God: that God alone is Lord and alone deserves worship."),
    "shirk": (["shirk"], "associating partners with God polytheism idolatry",
              "Associating partners with God; the opposite of tawhid."),
    "dhikr": (["dhikr", "zikr", "zikir"], "remembrance of God remembering glorify",
              "Remembrance of God, by heart and tongue."),
    "dua": (["dua", "du'a", "duaa"], "supplication prayer asking calling upon",
            "Supplication: calling on God and asking Him directly."),
    "salah": (["salah", "salat", "salaat"], "prayer ritual prayer pray",
              "The five daily ritual prayers."),
    "zakah": (["zakah", "zakat", "zakaat"], "obligatory charity alms poor due",
              "Obligatory annual alms on wealth above a threshold, given to set categories of people."),
    "sadaqah": (["sadaqah", "sadaqa", "sadaqat"], "charity voluntary charity giving alms",
                "Voluntary charity, given at any time and in any amount."),
    "sawm": (["sawm", "siyam", "siyaam"], "fasting fast",
             "Fasting: abstaining from food, drink and intimacy from dawn to sunset."),
    "hajj": (["hajj", "haj"], "pilgrimage Mecca",
             "The pilgrimage to Mecca, required once in a lifetime of those able."),
    "jihad al-nafs": (["jihad al-nafs", "mujahada", "mujahadah"], "struggle against the self ego desires",
                      "Struggling against one's own ego and desires."),
    "nafs": (["nafs"], "self soul ego desires",
             "The self or ego, with its desires."),
    "qalb": (["qalb"], "heart",
             "The heart: in Islamic writing, the seat of faith, intention and understanding."),
    "akhirah": (["akhirah", "akhira", "aakhirah"], "hereafter afterlife Last Day",
                "The Hereafter: life after death, judgement, Paradise and Hell."),
    "dunya": (["dunya", "dunyaa"], "this world worldly life",
              "This worldly life, as opposed to the Hereafter."),
    "qadar": (["qadar", "qadr", "qada"], "destiny decree predestination fate",
              "Divine decree: that everything happens by God's knowledge and will."),
    "rahmah": (["rahmah", "rahma"], "mercy compassion merciful",
               "Mercy."),
    "adab": (["adab"], "etiquette manners courtesy conduct",
             "Good manners and proper conduct."),
    "akhlaq": (["akhlaq", "akhlaaq", "khuluq"], "character morals ethics",
               "Character and morals."),
    "hasad": (["hasad"], "envy jealousy",
              "Envy: wishing that another person lose a blessing."),
    "kibr": (["kibr", "takabbur"], "pride arrogance conceit",
             "Arrogance: rejecting the truth and looking down on people."),
    "riya": (["riya", "riyaa", "riya'"], "showing off ostentation",
             "Showing off: doing good deeds to be seen by people."),
    "ghibah": (["ghibah", "gheebah", "ghiba"], "backbiting gossip",
               "Backbiting: saying something true about an absent person that they would dislike."),
    "fitnah": (["fitnah", "fitna"], "trial tribulation test strife",
               "A trial or tribulation; also discord and strife."),
    "ibtila": (["ibtila", "ibtilaa", "bala"], "trial test affliction hardship",
               "A test or affliction sent as a trial."),
    "sirah": (["sirah", "seerah"], "biography of the Prophet life of the Prophet",
              "The biography of the Prophet Muhammad."),
    "hijrah": (["hijrah", "hijra"], "emigration migration to Medina",
               "The Prophet's emigration from Mecca to Medina in 622 CE."),
}

_SPELLINGS = {fold(s): key for key, (spellings, _, _) in TERMS.items() for s in spellings}


def find_terms(text: str) -> list[str]:
    """Glossary keys mentioned in the text (diacritics and case ignored)."""
    t = fold(text)
    found = []
    for spelling, key in _SPELLINGS.items():
        if re.search(rf"(?<![a-z]){re.escape(spelling)}(?![a-z])", t) and key not in found:
            found.append(key)
    return found


def expand(question: str) -> str:
    """Append English equivalents of any Arabic term in the question (F12)."""
    extra = [TERMS[k][1] for k in find_terms(question)]
    return question if not extra else f"{question} ({'; '.join(extra)})"


def lookup(term: str) -> tuple[str, str, str] | None:
    """(key, english, gloss) for a term or any of its spellings."""
    key = _SPELLINGS.get(fold(term).strip())
    return (key, TERMS[key][1], TERMS[key][2]) if key else None
