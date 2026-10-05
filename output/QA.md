# QA report (2026-10-05)

## 1. Random re-check of 10 documents

| file | resort | resort match | type stored | type re-check | ok |
|---|---|---|---|---|---|
| 2026_Easter-Brochure-2026.pdf | Milaidhoo Island Maldives | Y | calendar | calendar | Y |
| 2026_International-Coffee-Day.pdf | Dhigali Maldives | N | dining_menu | dining_menu | Y |
| 2019_Nonna-Beverage-Menu-Updated18042023.pdf | Kagi Maldives Resort and Spa | N | dining_menu | dining_menu | Y |
| 2024_Kebab-Kurry-Menu.pdf | The Marina at Crossroads Maldi | N | dining_menu | dining_menu | Y |
| 2019_Factsheet-Kuramathi-Maldives.pdf | Kuramathi Maldives | Y | factsheet | factsheet | Y |
| 2025_Veli-Factsheet-W25-26S26Ver17062025.pdf | Veligandu Maldives Resort Isla | N | factsheet | factsheet | Y |
| 2024_Bandos-Dive-Menu-2024.pdf | Bandos Maldives | Y | dining_menu | dining_menu | Y |
| 2025_Karol_Menu.pdf | Amilla Fushi | N | dining_menu | dining_menu | Y |
| 2025_cmf_cs_advance_cleanse_itinerary.pdf | Como Maalifushi | Y | dining_menu | dining_menu | Y |
| 2022_Ilsy-Catamaran-Finolhu-01-Dec-2021-to-01-Mar- | Finolhu Baa Atoll Maldives | Y | dive_prices | dive_prices | Y |

Resort match confirmed: 5/10; doc type stable: 10/10

## 2. Latest factsheets: edition year vs text

112/119 consistent.

| resort | file | year | source | years in text | ok |
|---|---|---|---|---|---|
| Constance Moofushi Resort | 2023_moofushi-factsheet-en-24april2023.pdf | 2023 | filename | [2010] | N |
| JW Marriott Maldives Resort &  | 2023_JW-Marriott-Maldives-Resort-Spa-Factshee | 2023 | filename | [2019] | N |
| Nova Maldives | 2022_Factsheet-Nova-Maldives-NEO.pdf | 2022 | pdf-date | [2021] | N |
| Ozen By Atmosphere At Maadhoo | 2025_OZEN-LIFE-MAADHOO-Fact-Sheet-2025.pdf | 2025 | filename | [2016] | N |
| Royal Island Resort and Spa | 2026_Royal - Factsheet Jun 2026.pdf | 2026 | filename | [2024] | N |
| Villa Nautica Paradise Island | 2026_Villa Nautica - Factsheet Jul 2026.pdf | 2026 | filename | [2025] | N |
| Diamonds Thudufushi Beach and  | 2026_Diamonds-Leisure-Beach-Golf-Resort-Fact- | 2026 | filename | [2025] | N |

## 3. Workbook recalculation

`{"recalculated": true, "formula_errors": 0, "examples": []}`

Coverage sheet, first rows after recalculation:

- ['#', 'Resort', 'Official site status', 'factsheet (latest yr)', 'wedding (latest yr)', 'events (latest yr)', 'map (latest yr)', 'dive_map (latest yr)']
- [1, 'Six Senses Laamu', 'blocked', None, None, None, None, None]
- [2, 'Filitheyo Island Resort', 'blocked-partial', None, None, None, None, None]
- [3, 'Adaaran Select Hudhuranfushi', 'ok', 2026, 2027, 2027, 2025, None]

## 4. Resorts without a factsheet (60)

- 1. Six Senses Laamu
- 2. Filitheyo Island Resort
- 12. Thulhagiri Island Resort & Spa
- 13. Sandies Bathala
- 14. Baglioni Resort Maldives
- 16. JW Marriott Kaafu Atoll Island Resort
- 17. Rihiveli Maldives Resort
- 19. The Residence Maldives
- 20. The Residence Maldives At Dhigurah
- 24. Canareef Resort Maldives
- 29. Dheruhfinolhu by Jawakara Islands Maldives
- 36. Coastline Residences
- 42. Dhiggiri Tourist Resort
- 44. Hard Rock Hotel Maldives
- 47. Park Hyatt Maldives, Hadahaa
- 51. Emerald Maldives Resort & Spa Fasmendho
- 53. Cinnamon Hakuraa Huraa Maldives
- 54. Emerald Faarufushi Resort & Spa
- 55. Fihaalhohi Maldives
- 56. Four Seasons Resort Maldives at Kuda Huraa
- 57. Fushifaru Maldives
- 60. Reethi Beach Resort
- 63. Hondaafushi Island Resort
- 64. Radisson Blu Resort Maldives
- 77. Atmosphere Kanifushi Maldives
- 80. Raaya by Atmosphere
- 83. Mabinhura by Jawakara Islands Maldives
- 84. Alimatha Aquatic Resort
- 86. Four Seasons Private Island Maldives at Voavah
- 87. Four Seasons Resort Maldives at Landaa Giraavaru
- 88. Holiday Inn Resort Kandooma Maldives
- 93. Maayafushi Tourist Resort
- 98. Madifushi Private Island
- 101. Club Med Finolhu Villas
- 104. Medhufushi Island Resort
- 107. The Westin Maldives Miriandhoo Resort
- 108. Rahaa Resort
- 110. Furaveri Island Resort & Spa
- 113. Mercure Maldives Kooddoo
- 114. Gangehi Island Resort
- 115. Oblu Select by Atmosphere at Sangeli
- 119. Outrigger Maldives Maafushivaru Resort
- 122. Avani + Fares Maldives
- 124. Aanugandu Island Resort
- 125. Gili Lankanfushi
- 129. Riu Atoll and Riu Palace Maldivas
- 130. Robinson Noonu
- 131. Robinson Maldives
- 133. Oblu By Atmosphere at Helengeli
- 137. Soneva Secret
- 138. Varu Island Resort
- 142. Safari Island
- 144. South Palm Resort Maldives
- 149. Biyaadhoo Island Resort
- 151. Coco Palm Dhunikolhu
- 156. Drift Theluveliga Retreat
- 161. Ellaidhoo Maldives By Cinnamon
- 162. The Marina at Crossroads Maldives
- 167. Milaidhoo Island Maldives
- 181. Yash Nature Resort

## 5. Resorts whose newest factsheet is older than 2024 (48)

- 5. Bolifushi Island Resort (2023)
- 6. Joali Being Bodufushi (2023)
- 7. Joali Muravandhoo (2023)
- 10. Dreamland - The Unique Sea & Lake Resort/Spa (2023)
- 11. Angaga Island Resort and Spa (2018)
- 15. Alila Kothaifaru Maldives (2022)
- 18. JW Marriott Maldives Resort & Spa (2023)
- 27. Grand Park Kodhipparu Maldives (2023)
- 30. Hurawalhi Island Resort (2023)
- 31. Innahura Maldives Resort (2021)
- 37. The Ritz Carlton Maldives Fari Islands (2021)
- 39. NH Collection Maldives Havodda Resort (2018)
- 40. Le Méridien Maldives Resort and Spa (2021)
- 58. Sirru Fen Fushi (2023)
- 61. Equator Village (2023)
- 62. Cora Cora Maldives (2021)
- 72. Embudhu Village (2023)
- 74. Kandolhu Island Maldives (2019)
- 76. Hideaway Beach Resort and Spa at Dhonakulhi Island Maldives (2020)
- 82. Ifuru Island Maldives (2023)
- 89. Inter Continental Maldives Maamunagau (2020)
- 90. Six Senses Kanuhura (2018)
- 91. Lily Beach Resort (2019)
- 95. Malahini Kuda Bandos (2017)
- 102. W Maldives (2019)
- 103. Sheraton Maldives Full Moon Resort & Spa (2018)
- 106. Anantara Kihavah Villas (2022)
- 109. Constance Moofushi Resort (2023)
- 112. Nika Island Resort and Spa (2020)
- 116. Nova Maldives (2022)
- 121. Cocoa Island (2022)
- 123. Pullman Maldives Maamutaa Resort (2020)
- 128. One & Only Reethi Rah, Maldives (2019)
- 132. Noku Maldives (2021)
- 134. The St. Regis Vommuli Resort, Maldives (2021)
- 139. Kudafushi Resort & Spa (2019)
- 141. Soneva Fushi Resort (2023)
- 143. Soneva Jani (2019)
- 145. Anantara Resort and Spa Maldives (2023)
- 146. Anantara Veli and Naladhu (2023)
- 150. Coco Bodu Hithi (2020)
- 153. Taj Coral Reef Resort and Spa (2021)
- 154. Taj Exotica Resort & Spa Maldives (2021)
- 155. Constance Halaveli Resort (2023)
- 159. Cinnamon Dhonveli Maldives (2023)
- 160. Cinnamon Velifushi Maldives (2023)
- 171. Velaa Private Island Maldives (2019)
- 172. Mirihi Island Resort (2017)
