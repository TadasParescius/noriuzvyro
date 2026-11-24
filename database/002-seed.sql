-- Fictional data for the laboratory demonstration. No real customer contacts.
-- The setup script runs this only when ALL three domain tables are empty.
INSERT INTO quarries(name, city, address, phone, description, latitude, longitude) VALUES
('Šilo karjeras', 'Kaunas', 'Demonstracinė Šilo g. 1, Kauno r.', '+37060000001', 'Mokomasis smėlio ir žvyro karjeras Kauno rajone.', 54.920100, 23.850100),
('Neries karjeras', 'Vilnius', 'Demonstracinė Neries g. 2, Vilniaus r.', '+37060000002', 'Mokomasis biriųjų medžiagų tiekėjas Vilniaus rajone.', 54.740200, 25.210200),
('Pajūrio karjeras', 'Klaipėda', 'Demonstracinė Pajūrio g. 3, Klaipėdos r.', '+37060000003', 'Mokomasis karjeras kelių ir aplinkos tvarkymui.', 55.740300, 21.250300),
('Saulės karjeras', 'Šiauliai', 'Demonstracinė Saulės g. 4, Šiaulių r.', '+37060000004', 'Mokomasis statybinio smėlio ir skaldos tiekėjas.', 55.980400, 23.350400),
('Nevėžio karjeras', 'Panevėžys', 'Demonstracinė Nevėžio g. 5, Panevėžio r.', '+37060000005', 'Mokomasis žvyro tiekėjas Panevėžio rajone.', 55.760500, 24.410500);

INSERT INTO offers(quarry_id, name, material_type, fraction, description, price_per_tonne_eur, available)
SELECT q.id, v.name, v.kind, v.fraction, v.description, v.price, v.available
FROM (VALUES
 ('Šilo karjeras', 'Plautas žvyras', 'gravel', '4–16 mm', 'Plautas žvyras drenažui ir aplinkos tvarkymui.', 18.50, true),
 ('Šilo karjeras', 'Sijotas smėlis', 'sand', '0–2 mm', 'Smulkus sijotas smėlis statybos darbams.', 12.00, true),
 ('Neries karjeras', 'Drenažinis žvyras', 'gravel', '8–32 mm', 'Stambus žvyras drenažo sluoksniui.', 21.00, true),
 ('Pajūrio karjeras', 'Granito skalda', 'crushed_stone', '16–32 mm', 'Granito skalda įvažiavimų pagrindui.', 32.00, true),
 ('Saulės karjeras', 'Užpylimo smėlis', 'sand', '0–4 mm', 'Smėlis sklypo lyginimui ir užpylimui.', 9.50, false),
 ('Nevėžio karjeras', 'Kelio žvyras', 'gravel', '0–32 mm', 'Žvyro mišinys vietinių kelių pagrindui.', 16.00, true)
) AS v(quarry_name, name, kind, fraction, description, price, available)
JOIN quarries q ON q.name = v.quarry_name;

INSERT INTO orders(offer_id, customer_name, email, phone, delivery_address, quantity_tonnes,
 unit_price_eur, will_be_home, unloading_instructions, payment_method, status)
SELECT o.id, v.customer, v.email, v.phone, v.address, v.quantity, o.price_per_tonne_eur,
 v.at_home, v.instructions, v.payment, v.status
FROM (VALUES
 ('Plautas žvyras', 'Jonas Pavyzdys', 'jonas@example.com', '+37060000101', 'Mokomoji g. 11, Kaunas', 10.000, true, '', 'cash', 'pending'),
 ('Plautas žvyras', 'Ieva Pavyzdė', 'ieva@example.com', '+37060000102', 'Mokomoji g. 12, Kaunas', 5.500, false, 'Išpilti pažymėtoje vietoje prie vartų.', 'card', 'confirmed'),
 ('Sijotas smėlis', 'Lukas Pavyzdys', 'lukas@example.com', '+37060000103', 'Mokomoji g. 13, Kaunas', 8.000, true, '', 'cash', 'delivered'),
 ('Drenažinis žvyras', 'Rasa Pavyzdė', 'rasa@example.com', '+37060000104', 'Mokomoji g. 14, Vilnius', 12.000, false, 'Išpilti ant mėlyno tento kieme.', 'card', 'pending'),
 ('Granito skalda', 'Tomas Pavyzdys', 'tomas@example.com', '+37060000105', 'Mokomoji g. 15, Klaipėda', 7.250, true, '', 'cash', 'confirmed'),
 ('Kelio žvyras', 'Austėja Pavyzdė', 'austeja@example.com', '+37060000106', 'Mokomoji g. 16, Panevėžys', 15.000, true, '', 'card', 'cancelled')
) AS v(offer_name, customer, email, phone, address, quantity, at_home, instructions, payment, status)
JOIN offers o ON o.name = v.offer_name;
