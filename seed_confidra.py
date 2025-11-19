# seed_confidra.py
from models import db, ConfidraMudiri

FAKULTET_DATA = {
    1: [
        "Mamadjanova Tuyg‘unoy Axmadjanovna",
        "Shodiyev Akbar Ashurovich",
        "Xoliyarov Erkin Chorshanbievich",
        "Juraev Xusan Atamuratovich"
    ],
    2: [
        "Eshqarayev Ulug’bek Choriyevich",
        "Eshkurbonov Sirojiddin Bozorovich",
        "Uralova Oysuluv Poyon qizi",
        "Zayniddin Radjabovich",
        "Sattarova Yelena Anatolevna",
        "Yormatov Faxriddin Joylovovich",
        "Ismoilov Bobur Tohirovich",
        "Salomov G‘ulom Yo‘ldoshevich",
        "Norkulova Shaxnoza Tulkinovna",
        "Usmonov Mansur Qurbonmurotovich"
    ],
    3: [
        "Rasulov Abdusamat Abdujabborovich",
        "Saidov Jasur Baxtiyarovich",
        "Kenjayev Yodgor Mamatkulovich",
        "Xolmurodov Inoyatullo Ismatulloyevich",
        "Pardayev Anvar Misirovich",
        "Sultonov Ravshan Komiljonovich",
        "Ruziyev Oybek Avlayevich",
        "Xudaykulov Babakul Karjavovich"
    ]
}

db.connect(reuse_if_open=True)

for fac_id, names in FAKULTET_DATA.items():
    for full_name in names:
        ConfidraMudiri.create(
            full_name=full_name,
            facultet_type=fac_id
        )

print("Seeder tugadi.")