# Projekto „Noriuzvyro“ ataskaita

## 1. Sprendžiamo uždavinio aprašymas

### 1.1. Sistemos paskirtis

Projekto tikslas – palengvinti žvyro, smėlio ir skaldos užsakymą, vienoje internetinėje svetainėje sujungiant pirkėjus, karjerus ir medžiagas pristatančius vairuotojus. Ateityje sistema galės būti papildyta kitomis biriųjų medžiagų kategorijomis.

Veikimo principas – platformą sudarys internetinė aplikacija ir aplikacijų programavimo sąsaja (API). Pirkėjas žemėlapyje pasirinks karjerą, medžiagą, jos frakciją bei apytikslį kiekį. Tuomet pasirinks vežėją, matys reisų skaičių, medžiagos ir pristatymo kainas. Užsakydamas nurodys kontaktus, pristatymo adresą ir atsiskaitymo būdą.

Sistemoje numatomos keturios rolės: pirkėjas, vairuotojas, karjero atstovas ir administratorius. Pirkėjas galės pirkti kaip svečias arba prisijungęs prie paskyros. Vairuotojas ir karjero atstovas turės atskiras valdymo aplinkas, o administratorius prižiūrės naudotojus ir skelbiamą informaciją.

### 1.2. Funkciniai reikalavimai

**Pirkėjas galės:**

1. Peržiūrėti karjerus žemėlapyje ir jų parduodamas medžiagas, kainas bei frakcijas

2. Pasirinkti medžiagą ir įvesti norimą apytikslį kiekį

3. Pasirinkti vairuotoją, palyginti vežimo kainas, sunkvežimių talpą ir reikalingų reisų skaičių

4. Užsiregistruoti, prisijungti, atsijungti arba pateikti užsakymą kaip svečias

5. Nurodyti el. paštą, telefono numerį ir pristatymo adresą

6. Pasirinkti, ar bus namuose. Jei nebus, privalomai parašyti, kur išpilti

7. Atsiskaityti kortele arba pasirinkti mokėjimą grynaisiais vairuotojui pristatymo metu

8. Pagal kontaktų prieigos taisykles susisiekti su karjeru ir vairuotoju

9. Gauti užsakymo

**Vairuotojas galės:**

1. Prisijungti prie savo valdymo aplinkos ir atnaujinti kontaktinį telefono numerį

2. Pridėti, redaguoti ir išjungti savo sunkvežimius

3. Nurodyti sunkvežimio matmenis, kėbulo tūrį ir maksimalią krovinio masę

4. Nustatyti vežimo kainas ir aptarnaujamą teritoriją

5. Peržiūrėti ir patvirtinti arba atmesti jam pateiktus užsakymus

6. Matyti patvirtinto pristatymo adresą, pirkėjo kontaktus ir išpylimo instrukciją

7. Pažymėti pristatymą atliktu ir užregistruoti atsiskaitymą grynaisiais

**Karjero atstovas galės:**

1. Prisijungti prie savo valdymo aplinkos

2. Nurodyti karjero pavadinimą, vietą žemėlapyje ir kontaktinį telefono numerį

3. Pridėti, redaguoti ir išjungti žvyro, smėlio, skaldos bei kitų medžiagų pasiūlymus

4. Nurodyti medžiagos kainą, pardavimo vienetą, frakciją ir prieinamumą

5. Peržiūrėti ir patvirtinti arba atmesti savo karjero užsakymus

6. Pažymėti medžiagą paruošta paimti ir susisiekti su pasirinktu vairuotoju

**Administratorius galės:**

1. Valdyti naudotojų paskyras ir jų roles

2. Patvirtinti vairuotojų ir karjerų atstovų paskyras bei blokuoti naudotojus

3. Šalinti netinkamus pasiūlymus ir tvarkyti medžiagų kategorijas

4. Peržiūrėti užsakymus bei mokėjimų būsenas ir spręsti veikimo problemas

Kontaktų prieiga: registruotas pirkėjas kontaktus matys prisijungęs. Svečias juos gaus pateikęs el. paštą, adresą bei telefoną ir apmokėjęs užsakymą kortele. Mokėjimui grynaisiais siūloma išimtis: kontaktai atveriami patvirtinus el. paštą ir užsakymą, nes atsiskaitoma tik pristatymo metu. Kitų pirkėjų asmens duomenys viešai nerodomi.

## 2. Sistemos architektūra

sistemos sudedamosios dalys ir technologijos:

1. Kliento pusė – React ir TypeScript: interaktyviai užsakymo formai ir naudotojų valdymo aplinkoms

2. Serverio pusė – Python ir FastAPI: REST API, prieigos teisėms ir užsakymų logikai

3. Duomenų bazė – PostgreSQL: naudotojams, pasiūlymams ir užsakymams saugoti

4. Žemėlapis – nežinau bus sugalvota darymo metu

5. Mokėjimai – nežinau bus sugalvota darymo metu

6. Diegimas – Linux serveris, Docker konteineriai

2.1 pav. pateikta sistemos diegimo diagrama. Sistema patalpinta „Microsoft Azure“ virtualioje mašinoje su Ubuntu 24.04 LTS operacine sistema, „Belgium Central“ regione. Atskiruose Docker konteineriuose veikia Caddy, Python su FastAPI ir PostgreSQL duomenų bazė. Caddy aptarnauja React aplikacijos failus, persiunčia API užklausas ir automatiškai valdo HTTPS sertifikatą. Duomenų bazė pasiekiama tik vidiniame Docker tinkle.

quarries
{
  "name": "Gynimo karjeras",
  "city": "Kaunas",
  "address": "Pavyzdžio g. 10, Kauno r.",
  "phone": "+37060000111",
  "description": "Smėlio ir žvyro karjeras.",
  "latitude": 54.9,
  "longitude": 23.9
}

offers
{
  "name": "Sijotas smėlis",
  "materialType": "sand",
  "fraction": "0-2 mm",
  "description": "Smulkus smėlis statybos darbams.",
  "pricePerTonneEur": 15,
  "available": true
}

orders
{
  "customerName": "Jonas Pavyzdys",
  "email": "jonas@example.com",
  "phone": "+37060000333",
  "deliveryAddress": "Pavyzdžio g. 25, Kaunas",
  "quantityTonnes": 2,
  "willBeHome": false,
  "unloadingInstructions": "Išpilti prie vartų ant tento.",
  "paymentMethod": "cash",
  "status": "pending"
}
