# QA report (2026-10-04)

## 1. Random re-check of 10 documents

| file | resort | resort match | type stored | type re-check | ok |
|---|---|---|---|---|---|
| 2026_PADI-Womens-Dive-Day-1.pdf | Dhigali Maldives | N | dive_prices | dive_prices | Y |
| 2024_RU-Bev-List.pdf | Ayada Maldives | Y | dining_menu | dining_menu | Y |
| 2025_Aarah-Ralu-A-la-carte-Menu-05.08.2025.pdf | Heritance Aarah | Y | dining_menu | dining_menu | Y |
| 2024_BM-Resort-Map-2024.pdf | Bandos Maldives | Y | map | map | Y |
| 2025_Emerald-Faarufushi-Brochure-Web.pdf | Emerald Faarufushi Resort & Sp | Y | brochure | brochure | Y |
| 2026_so_huahin_fitness_cycling_map_0226.pdf | SO/ Maldives | N | map | map | Y |
| 2019_kandolhu-maldives-factsheet.pdf | Kandolhu Island Maldives | Y | factsheet | factsheet | Y |
| 2026_Ralu-A-la-carte-Afernoon-menu.pdf | Heritance Aarah | N | dining_menu | dining_menu | Y |
| 2025_wedding-package-ssom-2024-2025-direct.pdf | Sun Siyam Olhuveli Maldives | Y | wedding | wedding | Y |
| 2023_Fact-sheet-Velifushi.pdf | Cinnamon Velifushi Maldives | Y | factsheet | factsheet | Y |

Resort match confirmed: 7/10; doc type stable: 10/10

## 2. Latest factsheets: edition year vs text

96/109 consistent.

| resort | file | year | source | years in text | ok |
|---|---|---|---|---|---|
| Dhawa Ihuru | 2025_DHMVIH-Fact-Sheet.pdf | 2025 | pdf-date | [2023, 2024] | N |
| Cocoa Island | 2019_COMO-Cocoa-Island-Fact-Sheet-2019.pdf | 2019 | filename | [2013, 2015, 2016] | N |
| Como Maalifushi | 2019_COMO-Maalifushi-Fact-Sheet.pdf | 2019 | pdf-date | [2014, 2015] | N |
| Constance Moofushi Resort | 2023_moofushi-factsheet-en-24april2023.pdf | 2023 | filename | [2010] | N |
| Finolhu Baa Atoll Maldives | 2021_Finolhu-2021FactSheet_English-1.pdf | 2021 | filename | [2020] | N |
| Joali Being Bodufushi | 2025_JoaliBeing_Factsheet_V13.pdf | 2025 | pdf-date | [2023] | N |
| JW Marriott Maldives Resort &  | 2023_JW-Marriott-Maldives-Resort-Spa-Factshee | 2023 | filename | [2019] | N |
| Le Méridien Maldives Resort an | 2022_Resort-Factsheet-Le-Meridien-Maldives.pd | 2022 | pdf-date | [2018, 2021] | N |
| Lily Beach Resort | 2020_LilyBeach-Factsheet-Resort-NEO.pdf | 2020 | pdf-date | [2019] | N |
| Nova Maldives | 2022_Factsheet-Nova-Maldives-NEO.pdf | 2022 | pdf-date | [2021] | N |
| Ozen By Atmosphere At Maadhoo | 2025_OZEN-LIFE-MAADHOO-Fact-Sheet-2025.pdf | 2025 | filename | [2016] | N |
| Sun Siyam Vilu Reef Maldives | 2019_Fact-Sheet-2019.pdf | 2019 | filename | [2018] | N |
| Velassaru Maldives | 2020_velasaru_resort_factsheet_rdc.pdf | 2020 | pdf-date | [2015] | N |

## 3. Workbook recalculation

`{"recalculated": false, "error": "soffice produced no file"}`


## 4. Resorts without a factsheet (69)

- 2. Filitheyo Island Resort
- 12. Thulhagiri Island Resort & Spa
- 13. Sandies Bathala
- 14. Baglioni Resort Maldives
- 16. JW Marriott Kaafu Atoll Island Resort
- 17. Rihiveli Maldives Resort
- 19. The Residence Maldives
- 20. The Residence Maldives At Dhigurah
- 24. Canareef Resort Maldives
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
- 61. Equator Village
- 63. Hondaafushi Island Resort
- 64. Radisson Blu Resort Maldives
- 72. Embudhu Village
- 73. Summer Island Maldives
- 77. Atmosphere Kanifushi Maldives
- 80. Raaya by Atmosphere
- 84. Alimatha Aquatic Resort
- 86. Four Seasons Private Island Maldives at Voavah
- 87. Four Seasons Resort Maldives at Landaa Giraavaru
- 88. Holiday Inn Resort Kandooma Maldives
- 93. Maayafushi Tourist Resort
- 94. Reethi Faru Resort
- 98. Madifushi Private Island
- 100. Club Med Kanifinolhu
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
- 123. Pullman Maldives Maamutaa Resort
- 124. Aanugandu Island Resort
- 125. Gili Lankanfushi
- 127. Oaga Art Resort
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
- 152. Makunudu Island
- 156. Drift Theluveliga Retreat
- 157. The Nautilus Maldives
- 161. Ellaidhoo Maldives By Cinnamon
- 162. The Marina at Crossroads Maldives
- 167. Milaidhoo Island Maldives
- 170. Cocogiri Island Resort
- 176. Villa Park Sun Island
- 177. Royal Island Resort and Spa
- 181. Yash Nature Resort

## 5. Resorts whose newest factsheet is older than 2024 (62)

- 5. Bolifushi Island Resort (2023)
- 7. Joali Muravandhoo (2023)
- 10. Dreamland - The Unique Sea & Lake Resort/Spa (2023)
- 11. Angaga Island Resort and Spa (2018)
- 15. Alila Kothaifaru Maldives (2022)
- 18. JW Marriott Maldives Resort & Spa (2023)
- 27. Grand Park Kodhipparu Maldives (2022)
- 30. Hurawalhi Island Resort (2023)
- 31. Innahura Maldives Resort (2021)
- 37. The Ritz Carlton Maldives Fari Islands (2021)
- 39. NH Collection Maldives Havodda Resort (2018)
- 40. Le Méridien Maldives Resort and Spa (2022)
- 58. Sirru Fen Fushi (2023)
- 62. Cora Cora Maldives (2021)
- 65. Cheval Blanc Randheli (2022)
- 66. Como Maalifushi (2019)
- 71. Kagi Maldives Resort and Spa (2023)
- 74. Kandolhu Island Maldives (2019)
- 75. Kandima Maldives (2019)
- 76. Hideaway Beach Resort and Spa at Dhonakulhi Island Maldives (2020)
- 82. Ifuru Island Maldives (2023)
- 89. Inter Continental Maldives Maamunagau (2020)
- 90. Six Senses Kanuhura (2018)
- 91. Lily Beach Resort (2020)
- 95. Malahini Kuda Bandos (2017)
- 97. Angsana Resort & Spa Maldives - Velavaru (2023)
- 102. W Maldives (2019)
- 103. Sheraton Maldives Full Moon Resort & Spa (2018)
- 106. Anantara Kihavah Villas (2021)
- 109. Constance Moofushi Resort (2023)
- 111. Huvafenfushi Maldives (2020)
- 112. Nika Island Resort and Spa (2020)
- 116. Nova Maldives (2022)
- 118. Sun Siyam Iru Veli Maldives (2021)
- 121. Cocoa Island (2019)
- 126. Centara Grand Island Resort & Spa Maldives (2019)
- 128. One & Only Reethi Rah, Maldives (2019)
- 132. Noku Maldives (2021)
- 134. The St. Regis Vommuli Resort, Maldives (2021)
- 135. Diamonds Thudufushi Beach and Water Villas (2019)
- 136. Finolhu Baa Atoll Maldives (2021)
- 139. Kudafushi Resort & Spa (2019)
- 141. Soneva Fushi Resort (2019)
- 143. Soneva Jani (2019)
- 145. Anantara Resort and Spa Maldives (2023)
- 146. Anantara Veli and Naladhu (2023)
- 147. Sun Siyam Vilu Reef Maldives (2019)
- 148. Sun Siyam Iru Fushi Maldives (2019)
- 150. Coco Bodu Hithi (2020)
- 153. Taj Coral Reef Resort and Spa (2021)
- 154. Taj Exotica Resort & Spa Maldives (2021)
- 155. Constance Halaveli Resort (2023)
- 159. Cinnamon Dhonveli Maldives (2023)
- 160. Cinnamon Velifushi Maldives (2023)
- 163. Adaaran Prestige Vadoo (2023)
- 164. Baros Maldives (2022)
- 165. Velassaru Maldives (2020)
- 166. Kuramathi Maldives (2019)
- 171. Velaa Private Island Maldives (2019)
- 172. Mirihi Island Resort (2017)
- 173. Kurumba Maldives (2019)
- 178. Diamonds Athuruga Beach & Water Villas (2019)
