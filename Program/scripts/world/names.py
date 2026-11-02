"""Name banks for generated residents. Run `python scripts/world/names.py` to rewrite the shipped JSON.

Each bank is a set of groups, each with given names and family names that commonly go together. An underscore joins a two-word name. A city picks a
bank (by default from its era) and may weight the groups; real cities weight them by rough local estimates.
Lists favour ordinary names people actually had in the period and avoid stock fantasy names.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import peoples  # noqa: E402  (beastkin, fantasy humanoids and other peoples, each with its own naming scheme)

OUT = Path(__file__).resolve().parents[2] / 'dungeon' / 'world' / 'data' / 'names.json'
LIFESPANS = OUT.with_name('lifespans.json')


def group(feminine, masculine, neutral, family, cultures=None):
    made = {key: list(dict.fromkeys(word.replace('_', ' ') for word in words.split()))
            for key, words in (('feminine', feminine), ('masculine', masculine), ('neutral', neutral),
                               ('family', family))}
    return made | {'cultures': cultures or {}}


# How each modern heritage group takes given names from the popular names of the person's birth year
# (given_names.py). `local` is the city's own country (the United States for the built-in cities); a
# culture with its own family names supplies the family name too. The given-name lists below remain for
# settings outside those years.
CULTURES = {
    'anglo': {'local': 1},
    'black-american': {'us-black': 0.6, 'local': 0.4},
    'hispanic': {'us-hispanic': 0.6, 'local': 0.25, 'mexico': 0.15},
    'caribbean': {'jamaica': 0.4, 'haiti': 0.3, 'us-black': 0.3},
    'east-asian': {'local': 0.45, 'china': 0.15, 'korea': 0.12, 'vietnam': 0.12, 'philippines': 0.1, 'japan': 0.06},
    'south-asian': {'india': 0.65, 'local': 0.35},
    'jewish': {'local': 0.8, 'israel': 0.2},
    'italian': {'local': 0.8, 'italy': 0.2},
    'irish': {'local': 0.75, 'ireland': 0.25},
    'slavic': {'poland': 0.4, 'russia': 0.35, 'local': 0.25},
    'arabic': {'arab': 0.8, 'local': 0.2},
    'west-african': {'nigeria': 0.6, 'ghana': 0.4},
    'german': {'local': 0.65, 'germany': 0.35},
    'french-canadian': {'local': 0.55, 'france': 0.45},
}


MODERN = {
    # source: US Census Bureau surname file (2000 Census, rank and race/Hispanic shares, via fivethirtyeight/data most-common-name/surnames.csv; the 2010 table ranks near-identically): most common surnames in rank order, skipping majority-Hispanic, majority-Asian and majority-Black names
    'anglo': group(
        'Emily Sarah Jessica Megan Lauren Hannah Abigail Rachel Katherine Molly Claire Allison Heather Amanda '
        'Erin Caroline Madison Paige Natalie Brooke',
        'Michael Matthew Ryan Andrew Tyler Kyle Brian Justin Jacob Benjamin Nathan Zachary Travis Cody Luke '
        'Daniel Adam Scott Colin Garrett',
        'Jordan Taylor Morgan Casey Riley Avery Quinn Parker',
        'Smith Johnson Miller Davis Wilson Anderson Taylor Thomas Moore Martin Thompson White Clark Lewis '
        'Walker Hall Allen Young King Wright Hill Green Baker Adams Nelson Carter Mitchell Roberts Turner '
        'Phillips Campbell Parker Evans Edwards Collins Stewart Morris Rogers Cook Bennett Williams Brown Jones '
        'Jackson Harris Robinson Scott Morgan Murphy Peterson Cooper Reed Bailey Bell Kelly Howard Ward Cox '
        'Richardson Wood Watson Brooks Gray James Hughes Price Myers Long Foster Sanders Ross Powell Sullivan '
        'Russell Jenkins Perry Butler Barnes Fisher Henderson Coleman Simmons Patterson Jordan Reynolds '
        'Hamilton Graham Alexander Wallace Griffin West Cole Hayes Gibson Bryant Ellis Stevens Murray Ford '
        'Marshall Owens McDonald Harrison Kennedy Wells Woods Olson Webb Tucker Freeman Burns Henry Snyder '
        'Simpson Crawford Porter Mason Shaw Gordon Wagner Hunter Hicks Dixon Hunt Palmer Robertson Black Holmes '
        'Stone Meyer Boyd Mills Warren Fox Rose Rice Schmidt Ferguson Nichols Ryan Weaver Daniels Stephens '
        'Gardner Payne Kelley Dunn Pierce Arnold Spencer Peters Hawkins Grant Hansen Hoffman Hart Elliott '
        'Cunningham Knight Bradley Carroll Hudson Duncan Armstrong Berry Andrews Johnston Ray Lane Riley '
        'Carpenter Perkins Richards Willis Matthews Chapman Lawrence Watkins Wheeler Larson Carlson Harper '
        'George Greene Burke Morrison Jacobs Lawson Franklin Lynch Bishop Carr Austin Gilbert Jensen Williamson '
        'Montgomery Harvey Oliver Howell'),
    # source: US Census Bureau surname file (2000 Census, rank and race/Hispanic shares, via fivethirtyeight/data most-common-name/surnames.csv; the 2010 table ranks near-identically) for the common shared surnames and the majority-Black ones (Washington, Jefferson, Gaines, Mack, Singleton, Banks, Mosley); the rest general knowledge (estimate)
    'black-american': group(
        'Aaliyah Jasmine Brianna Destiny Imani Kiara Tiana Ebony Monique Danielle Alexis Nia Janelle Keisha '
        'Simone Tamika Aisha Jada Kayla Shanice',
        'Marcus Darnell Jamal Terrence Andre Malik DeShawn Tyrone Isaiah Jalen Darius Cedric Elijah Xavier '
        'Corey Reginald Lamar Devin Jerome Maurice',
        'Jordan Cameron Peyton Sydney Kendall',
        'Washington Jefferson Jackson Robinson Harris Coleman Brooks Bryant Freeman Banks Gaines Dawson Mosley '
        'Carter Simmons Henderson Gibson Holloway Ellis Hayes Booker Pryor Battle Moton Tolliver Williams '
        'Johnson Smith Jones Brown Davis Thomas Taylor Wilson Moore White Lewis Walker Thompson Jenkins Allen '
        'Wright Scott Green Young King Hill Butler Mitchell Hall Anderson Martin Wallace Bell Joseph Turner '
        'Edwards Grant Perry Howard Hunter Ford Barnes Hawkins Jordan Owens Woods Watkins Franklin Sims Glover '
        'Dixon Mack Singleton Ware Dorsey Rivers Hairston Merriweather Calhoun McNeil Gaskins Ingram Hampton '
        'Tate Wiggins Flowers Houston Pittman Graves Hines Roberson Bethea Ruffin Alston Whitfield Mayfield '
        'Bynum Dukes Mobley'),
    # source: US Census Bureau surname file (2000 Census, rank and race/Hispanic shares, via fivethirtyeight/data most-common-name/surnames.csv; the 2010 table ranks near-identically): surnames over 85% Hispanic, in rank order
    'hispanic': group(
        'Maria Sofia Valentina Camila Daniela Gabriela Isabella Lucia Mariana Ximena Paola Adriana Veronica '
        'Yesenia Alejandra Catalina Elena Rosa Natalia Andrea',
        'Jose Luis Carlos Juan Miguel Alejandro Diego Javier Mateo Santiago Rafael Eduardo Andres Fernando '
        'Ricardo Hector Emilio Julio Ivan Raul',
        'Guadalupe Cruz Ariel Alexis',
        'Garcia Rodriguez Martinez Hernandez Lopez Gonzalez Perez Sanchez Ramirez Torres Flores Rivera Gomez '
        'Diaz Morales Reyes Cruz Ortiz Gutierrez Chavez Ramos Mendoza Ruiz Alvarez Castillo Jimenez Vargas '
        'Romero Herrera Medina Aguilar Vega Castro Delgado Navarro Fuentes Cabrera Espinoza Salazar Ibarra '
        'Gonzales Soto Rios Vasquez Sandoval Guerrero Moreno Silva Pena Valdez Mendez Guzman Munoz Garza '
        'Contreras Maldonado Estrada Alvarado Nunez Santiago Dominguez Marquez Padilla Rojas Figueroa Acosta '
        'Luna Molina Campos Avila Juarez Duran Miranda Carrillo Mejia Ayala Leon Robles Salinas Solis Lara '
        'Trujillo Aguirre Pacheco Cervantes Ochoa Velasquez Montoya Cardenas Colon Serrano Calderon Gallegos '
        'Guerra Rosales Castaneda Trevino Villarreal Suarez Macias'),
    # source: name_sources/haiti.txt and jamaica.txt surname rankings (surnam.es), plus Indo-Caribbean surnames from general knowledge (estimate)
    'caribbean': group(
        'Marjorie Nadege Shanelle Kerry-Ann Fabienne Roseline Tamara Natasha Chantal Sabrina Mirlande Shauna',
        'Jean Pierre Ricardo Fritz Damian Oneil Kemar Junior Wesley Dwayne Patrice Andre',
        'Rene Dominique Claude',
        'Joseph Pierre Jean-Baptiste Charles Louis Etienne Desir Baptiste Campbell Brown Williams Thompson Reid '
        'Francis Clarke Gordon Morgan Henry Barrett Grant Jean Paul Michel Noel Philippe Augustin Alexis '
        'Toussaint Celestin Moise Laguerre Dorvil Cadet Fils-Aime Petit-Frere Saint-Louis Jean-Louis Pierre- '
        'Louis Lafortune Exantus Antoine Jules Destin Delva Germain Remy Bien-Aime Thermidor Hyppolite Mathurin '
        'Smith Johnson Edwards Bailey Robinson Lewis Scott Walker Wright Green Allen Hall Stewart Bennett '
        'Spence McKenzie Gayle Samuels Malcolm Powell Daley Hylton Mullings Rowe Hinds Blake Ricketts Beckford '
        'Lindo Facey Chambers Stephenson Sinclair Forbes Lawrence Simpson Dixon Wilson Richards Graham Hamilton '
        'James Murray Palmer Watson Wallace Persaud Ramdass Rampersad Mohammed'),
    # source: US Census Bureau surname file (2000 Census, rank and race/Hispanic shares, via fivethirtyeight/data most-common-name/surnames.csv; the 2010 table ranks near-identically) for the majority-Asian names (Nguyen, Kim, Chen, Wong, Chang, Yang, Lam ...); the rest from name_sources china/korea/vietnam/japan/philippines rankings and general knowledge (estimate)
    'east-asian': group(
        'Grace Michelle Christine Jennifer Linda Amy Vivian Joyce Angela Mei Ji-woo Seo-yeon Yuki Hana Thao '
        'Linh Maricel Kristine Jasmine Lily',
        'Kevin Eric David Brian Steven Andrew Jason Daniel Ken Hiro Min-jun Ji-ho Wei Jun Minh Tuan Paolo '
        'Marlon Ryan Jonathan',
        'Kai Sam Jin',
        'Lee Kim Park Choi Chen Wang Li Zhang Liu Huang Wu Lin Nguyen Tran Le Pham Hoang Tanaka Suzuki Nakamura '
        'Yamamoto Santos Reyes Cruz Bautista Dela_Cruz Garcia Mendoza Villanueva Wong Chang Yang Chan Lam Ho '
        'Zhou Xu Sun Ma Zhu Hu Guo He Lu Luo Gao Liang Zheng Tang Song Han Yu Cheng Cheung Chow Leung Tsai '
        'Huynh Vu Phan Truong Dang Bui Do Ngo Duong Ly Jung Kang Cho Yoon Jang Lim Shin Kwon Hwang Ahn Oh Seo '
        'Watanabe Ito Kobayashi Sato Takahashi Yoshida Yamada Sasaki Matsumoto Inoue Kimura Hayashi Ramos '
        'Flores Aquino Castillo Dizon Domingo Gonzales Manalo Ocampo'),
    # source: US Census Bureau surname file (2000 Census, rank and race/Hispanic shares, via fivethirtyeight/data most-common-name/surnames.csv; the 2010 table ranks near-identically) for Patel, Singh, Khan; the rest general knowledge of common Indian, Pakistani and Bangladeshi American surnames (estimate)
    'south-asian': group(
        'Priya Ananya Divya Neha Pooja Kavya Riya Shreya Aisha Fatima Meera Sana Anjali Nisha',
        'Arjun Rahul Vikram Rohan Sanjay Aditya Karthik Imran Omar Amit Nikhil Ravi Suresh Harpreet',
        'Kiran Sasha Arya',
        'Patel Shah Singh Kumar Sharma Gupta Reddy Rao Iyer Desai Mehta Joshi Chowdhury Khan Ahmed Malik '
        'Hussain Bhatt Menon Nair Kapoor Agarwal Gill Sandhu Kaur Jain Mishra Verma Chopra Bose Das Banerjee '
        'Chatterjee Mukherjee Ghosh Sen Pillai Krishnan Subramanian Srinivasan Narayanan Naidu Chaudhary Thakur '
        'Yadav Pandey Tiwari Srivastava Sinha Bhatia Arora Malhotra Khanna Sethi Grewal Dhillon Sidhu Bains '
        'Brar Parikh Modi Trivedi Pandya Vyas Amin Chauhan Patil Kulkarni Gandhi Bansal Garg Goel Mittal '
        'Siddiqui Qureshi Sheikh Rahman Hossain Islam Akhtar Butt Chaudhry Mirza Iqbal Rana Dutta Ali Bhakta '
        'Thakkar Raman Kohli Saini Varghese Thomas Mathew Dhaliwal Saxena Pandit Prasad Hegde'),
    # source: US Census Bureau surname file (2000 Census, rank and race/Hispanic shares, via fivethirtyeight/data most-common-name/surnames.csv; the 2010 table ranks near-identically) (Cohen, Schwartz, Klein, Weiss) and name_sources/jewish-diaspora.txt; ordering general knowledge (estimate)
    'jewish': group(
        'Rebecca Rachel Leah Miriam Hannah Shira Talia Naomi Ruth Ilana Dina Esther Abby Maya',
        'David Daniel Joshua Aaron Benjamin Noah Eli Ari Jonah Samuel Ethan Max Josh Adam',
        'Avi Shai',
        'Cohen Levy Goldberg Friedman Katz Schwartz Rosen Shapiro Klein Weiss Kaplan Stern Rosenberg Feldman '
        'Bernstein Horowitz Siegel Greenberg Adler Berman Levine Levin Goldstein Rosenthal Weinstein Gold Rubin '
        'Kaufman Silverman Hoffman Lieberman Marcus Diamond Abrams Segal Edelman Fine Frankel Glick Gross '
        'Hirsch Jacobs Kessler Lerner Mandel Perlman Reich Resnick Roth Sandler Schiff Singer Solomon Steinberg '
        'Strauss Wasserman Weinberg Weiner Wolf Zuckerman Zimmerman Abramson Applebaum Baum Blum Brenner '
        'Eisenberg Epstein Fink Freedman Ginsberg Goldman Goodman Grossman Halpern Heller Kahn Kramer Landau '
        'Margolis Rabinowitz Rosenblum Rubenstein Schulman Silver Sternberg Wexler Berkowitz Feinberg Moskowitz '
        'Lipman Teitelbaum Gottlieb Pollack Sachs Levinson Spector Fishman Jaffe Gelman'),
    # source: US Census Bureau surname file (2000 Census, rank and race/Hispanic shares, via fivethirtyeight/data most-common-name/surnames.csv; the 2010 table ranks near-identically) (Russo) and common Italian-American surnames from general knowledge (estimate)
    'italian': group(
        'Gina Theresa Angela Maria Francesca Nicole Christina Lisa Donna Gianna Marisa Teresa',
        'Anthony Vincent Joseph Dominic Salvatore Nicholas Frank Michael Carmine Paul Louis Joey',
        'Toni',
        "Russo Esposito Romano Ricci Marino Greco Bruno Gallo Conti DeLuca Costa Rizzo Lombardi Moretti "
        "Barbieri Fontana Caruso Ferrara Santoro Mancini Rossi Ferrari Colombo Martini Leone Longo Gentile "
        "Martinelli Vitale Lombardo Coppola DeSantis D'Angelo Marchetti Parisi Conte Ferraro Bianchi Marini "
        "Grasso Messina DeAngelis Palumbo Rinaldi Testa Morelli Amato Mazza Napolitano Castellano Cirillo "
        "D'Amico DeMarco Calabrese Falcone Ferrante Giordano Mancuso Marchese Natale Orlando Palermo Pagano "
        "Pellegrino Romeo Sabatino Salerno Santangelo Sorrentino Tedesco Zito Battaglia Benedetto Bianco "
        "Carbone Catalano Cavallo Colucci D'Alessandro DeRosa DiStefano Fiore Genovese Grillo Iacono Monaco "
        "Pace Palmieri Puglisi Riccio Ruggiero Spinelli Vaccaro Valente Vella Sanfilippo Rotella Scala Cuomo "
        "Gallucci"),
    # source: US Census Bureau surname file (2000 Census, rank and race/Hispanic shares, via fivethirtyeight/data most-common-name/surnames.csv; the 2010 table ranks near-identically) (Murphy, Kelly, Sullivan, Ryan, Burke, Walsh, Lynch, Brennan, OBrien, OConnor, Quinn, Doyle ...) and general knowledge (estimate)
    'irish': group(
        'Kathleen Maureen Colleen Siobhan Bridget Erin Fiona Shannon Kelly Megan Nora Deirdre',
        'Patrick Sean Kevin Brendan Liam Connor Declan Brian Kieran Owen Ryan Dennis',
        'Shea Rory',
        "Murphy Kelly O'Brien Sullivan Walsh Byrne Ryan O'Connor McCarthy Doyle Gallagher Kennedy Lynch Quinn "
        "Fitzgerald Brennan Donnelly Flanagan Kavanagh Callahan Burke Kelley Murray Brady Burns Collins "
        "Connolly Daly Dunn Dwyer Farrell Flynn Foley Hogan Kearney Keane Keegan Kenny McGrath McGuire "
        "McLaughlin McMahon McNamara Moran Mulligan Nolan O'Neill O'Donnell O'Sullivan O'Malley O'Reilly O'Hara "
        "O'Leary O'Rourke O'Shea O'Keefe Reilly Regan Sheehan Shea Sweeney Tierney Whelan Cullen Carroll Casey "
        "Cassidy Clancy Conway Corcoran Costello Cronin Curran Delaney Dempsey Devlin Donovan Doherty Duffy "
        "Egan Finnegan Fitzpatrick Hanley Healy Hennessy Higgins Hurley Keating Lennon Maguire Mahoney Malone "
        "McCann McCormick McDermott McKenna Moriarty Mullen Noonan Power"),
    # source: Polish, Russian, Ukrainian, Czech and South Slavic surnames common in the US, from name_sources poland/russia rankings and general knowledge (estimate)
    'slavic': group(
        'Katarzyna Anna Natalia Olga Irina Svetlana Ewa Magdalena Tatiana Yelena Agnieszka Daria',
        'Piotr Tomasz Pavel Dmitri Sergei Andrzej Marek Viktor Mikhail Stefan Bogdan Lukasz',
        'Sasha',
        'Kowalski Nowak Wisniewski Lewandowski Zielinski Kaminski Novak Petrov Ivanov Sokolov Volkov Popov '
        'Kovalenko Shevchenko Horvat Kozlowski Mazur Bondarenko Wojcik Kowalczyk Wozniak Szymanski Dabrowski '
        'Jankowski Wojciechowski Kwiatkowski Krawczyk Kaczmarek Piotrowski Grabowski Pawlowski Michalski Krol '
        'Wieczorek Jablonski Wroblewski Majewski Olszewski Malinowski Jaworski Adamczyk Dudek Nowicki Pawlak '
        'Gorski Witkowski Walczak Sikora Rutkowski Ostrowski Tomaszewski Zalewski Wrobel Sadowski Czarnecki '
        'Sawicki Sokolowski Kubiak Smirnov Kuznetsov Vasiliev Pavlov Fedorov Mikhailov Orlov Makarov Andreev '
        'Kovalev Morozov Lebedev Novikov Kozlov Egorov Romanov Zakharov Medvedev Antonov Karpov Melnyk '
        'Tkachenko Kravchenko Boyko Kovalchuk Lysenko Marchenko Savchenko Petrenko Moroz Dvorak Novotny Svoboda '
        'Cerny Prochazka Kucera Horak Jovanovic Petrovic Nikolic Markovic Kovacevic'),
    # source: name_sources/arab.txt rankings, weighted to Lebanese, Syrian, Palestinian, Egyptian and Iraqi Americans (Dearborn names such as Bazzi, Beydoun, Makki); general knowledge (estimate)
    'arabic': group(
        'Layla Nour Mariam Yasmin Rania Huda Salma Dalia Amira Zeinab Lina Hala',
        'Ahmed Mohamed Omar Khalid Youssef Karim Tariq Samir Hassan Ali Bilal Nabil',
        'Noor Rayan',
        'Haddad Khoury Nasser Saleh Hamdan Mansour Aziz Farah Rahman Abdullah Ibrahim Hassan Darwish Kassem '
        'Bakri Ali Ahmed Mohamed Hussein Saad Khalil Youssef Mahmoud Mustafa Ismail Abbas Said Salem Jaber Awad '
        'Khalaf Habib Nassar Najjar Sabbagh Shaheen Saba Hanna Boutros Gerges Mikhail Assaf Karam Maalouf Daher '
        'Ghanem Hakim Issa Jabbour Malouf Matar Nader Rizk Sleiman Tannous Touma Zogby Abboud Atallah Ayoub '
        'Barakat Bitar Elias Fares Hijazi Khalifa Masri Odeh Rashid Sharif Suleiman Tamimi Taha Zaki Zayed Omar '
        'Othman Hamad Hammoud Jamal Nasr Yassin Shaker Ghali Fawaz Hamza Bazzi Beydoun Makki Jaafar Fakih '
        'Haidar Ajami Saliba Halabi Shami Salameh Hashem Kamal Ramadan'),
    # source: name_sources/nigeria.txt and ghana.txt rankings plus common Senegalese, Guinean, Malian and Sierra Leonean surnames (general knowledge, estimate)
    'west-african': group(
        'Chiamaka Adaeze Ngozi Folake Amara Ifeoma Abena Ama Efua Yewande Kemi Zainab',
        'Chinedu Emeka Oluwaseun Tunde Kwame Kofi Kwabena Obinna Femi Ibrahima Moussa Segun',
        'Tobi Ayo',
        'Okafor Okonkwo Adeyemi Balogun Mensah Asante Owusu Boateng Diallo Traore Nwosu Eze Adebayo Ogunleye '
        'Danso Ndiaye Okoro Okeke Nwachukwu Obi Okoye Chukwu Igwe Anyanwu Nwankwo Udeh Ugwu Adeleke Adewale '
        'Afolabi Akinola Ajayi Alabi Babatunde Bello Ogundipe Oladipo Olatunji Olawale Oyewole Akande Ige Ojo '
        'Adekunle Adeniyi Adesina Abubakar Ibrahim Mohammed Musa Yusuf Etim Udo Effiong Bassey Ekpo Okon '
        'Agyeman Appiah Amoah Ansah Acheampong Addo Adjei Antwi Boakye Darko Frimpong Gyamfi Kyei Nkrumah Obeng '
        'Ofori Opoku Osei Quaye Sarpong Tetteh Yeboah Amponsah Annan Nyarko Agyei Badu Diop Fall Sow Camara '
        'Toure Keita Coulibaly Kone Sylla Bah Conteh Kamara Sesay Koroma Bangura Njoku'),
    # German Americans, the largest immigrant heritage of the 1920s, mostly in the Midwest, Pennsylvania and the
    # big northern cities: surnames as families kept or anglicized them (general knowledge, estimate)
    'german': group(
        'Anna Emma Frieda Gertrude Hilda Martha Bertha Elsie Lena Clara Louise Minnie',
        'Karl Otto Fritz Hans Herman Wilhelm Ernst Heinrich August Gustav Albert Walter',
        'Marion',
        'Schmidt Schneider Fischer Weber Meyer Wagner Becker Schulz Hoffmann Koch Bauer Richter Klein Wolf '
        'Schroeder Neumann Schwarz Zimmermann Braun Krueger Hofmann Hartmann Lange Schmitt Werner Krause Meier '
        'Lehmann Schmid Schulze Maier Koehler Herrmann Walter Mayer Huber Kaiser Fuchs Peters Lang Scholz Moeller '
        'Weiss Jung Hahn Vogel Friedrich Keller Guenther Frank Berger Winkler Roth Beck Lorenz Baumann Franke '
        'Albrecht Schuster Simon Ludwig Boehm Winter Kraus Martin Schumacher Kraemer Vogt Stein Jaeger Otto '
        'Sommer Gross Seidel Heinrich Brandt Haas Schreiber Graf Dietrich Ziegler Kuhn Kuehn Pohl Engel Horn '
        'Busch Bergmann Thomas Voigt Sauer Arnold Wolff Pfeiffer Heller Brenner Eckert Dreyer Muench Ritter '
        'Uhl Diehl Gerber Hauser Kessler Lutz Metzger Nagel Reinhardt Spengler Stahl Strauss Vogler Wendt'),
    # Québécois and Franco-American families (New England mill towns, Quebec): given names from the local and
    # French birth-year lists, family names always from these (general knowledge of the commonest Quebec
    # surnames, estimate)
    'french-canadian': group(
        'Marie Jeanne Yvonne Rita Cécile Thérèse Lucille Simone Monique Diane Nathalie Isabelle',
        'Joseph Jean Louis Henri Armand Lucien Marcel Roger Normand Gilles Denis Luc',
        'Claude Dominique',
        'Gagnon Roy Côté Bouchard Gauthier Morin Lavoie Fortin Gagné Ouellet Pelletier Bélanger Lévesque '
        'Bergeron Leblanc Paquette Girard Simard Boucher Caron Beaulieu Cloutier Dubé Poirier Fournier Lapointe '
        'Leclerc Lefebvre Poulin Thibault St-Pierre Nadeau Martin Landry Martel Bédard Grenier Lessard Bernier '
        'Richard Michaud Hébert Desjardins Couture Turcotte Lachance Parent Blais Gosselin Savard Proulx '
        'Beaudoin Demers Perreault Boudreau Lemieux Cyr Perron Dufour Dion Mercier Bolduc Bérubé Boisvert '
        'Langlois Ménard Thibodeau Ouellette Doucette Thériault Plourde Pépin Gendron Vachon Labrie Tremblay '
        'Rousseau Laflamme Comeau Arsenault Cormier Robichaud LeBlanc Benoit Cadieux Charron Daigle Gervais'),
}

for key, links in CULTURES.items():
    MODERN[key]['cultures'] = links
# Franco-American families kept their Quebec surnames whichever names their children were given.
MODERN['french-canadian']['own_family'] = True

VICTORIAN = {
    'english': group(
        'Mary Elizabeth Sarah Annie Alice Florence Emily Edith Ellen Ada Clara Harriet Louisa Martha Jane Emma '
        'Lucy Rose Kate Beatrice Agnes Lilian Violet Mabel Ethel Ann Margaret Eliza Charlotte Frances Fanny '
        'Caroline Catherine Susan Hannah Jessie Lily Amy Nellie Gertrude Maud Dorothy Minnie Elsie Lizzie '
        'Bertha Eleanor Isabella Amelia Julia Sophia Matilda Esther Rebecca Phoebe Rachel Ruth Maria Georgina '
        'Henrietta Adelaide Victoria Evelyn Gladys Hilda Ivy May Daisy Grace Kathleen Winifred Mildred Marion '
        'Laura Helen Lydia Selina Rosina Rosa Charity Emmeline Eva Ida Lottie Sophie Hester Leah Miriam Anne '
        'Jemima Keziah Dinah Bessie Polly Sally Betsy Nancy Rhoda Constance Olive',
        'William John George Thomas James Charles Henry Frederick Arthur Albert Alfred Walter Joseph Edward '
        'Robert Samuel Ernest Herbert Harry Richard Francis Percy Sidney Frank Edwin David Daniel Benjamin '
        'Isaac Edmund Edgar Harold Leonard Stanley Reginald Horace Hugh Matthew Peter Philip Stephen Michael '
        'Andrew Christopher Ralph Lewis Cecil Bertram Clement Cyril Claude Douglas Gilbert Howard Jacob Jesse '
        'Jonathan Joshua Lionel Louis Martin Maurice Nathaniel Oliver Oswald Owen Reuben Roland Rupert Tom '
        'Victor Wilfred Willie Abraham Amos Aaron Adam Alexander Ambrose Archibald Arnold Austin Basil Bernard '
        'Charlie Clarence Elijah Enoch Ezra Felix Gabriel Gerald Gordon Hubert Humphrey Jabez Jack Josiah '
        'Laurence Levi',
        '',
        'Smith Jones Williams Taylor Brown Davies Wilson Evans Thomas Johnson Roberts Robinson Wright Wood Hall '
        'Green Walker Hughes Edwards Lewis Turner Jackson Harris Clarke Cooper Ward Morris King Baker Harrison '
        'Allen Mitchell Hill Parker Price Bennett Cox Fletcher Pearce Webb Holloway Marsh Pritchard Thompson '
        'White Martin Moore Clark Young Scott Morgan Cook Phillips Shaw Lloyd Carter Collins Bell Murphy '
        'Richardson Marshall Simpson Ellis Adams Chapman Mason Rogers Stevens Hunt Butler Barnes Fisher Knight '
        'Harvey Russell Pearson Graham Gibson Kelly Dixon Hayes Wells Holmes Matthews Fox Grant Lawrence Mills '
        'Palmer Payne Saunders Spencer Stone Hunter Hart Andrews Atkinson Bailey Barker Bird'),
    'irish': group(
        'Bridget Catherine Margaret Honora Ellen Mary Johanna Nora Kate Julia Anne Winifred Eliza Sarah '
        'Elizabeth Annie Teresa Agnes Alice Delia Sabina Abina Kitty Hannah Jane Rose Josephine Maggie Lizzie '
        'Bessie Christina Susan Ann Mary_Ann Peggy Molly Nellie Katie Minnie Ellie Jenny Nancy Sally Biddy '
        'Kathleen Frances Fanny Isabella Sophia Martha Maria Cecilia Celia Monica Anastasia Deborah Penelope '
        'Una Grace Helena Helen Esther Emily Louisa Margery Barbara Lucy Letitia Philomena Bernadette Agatha '
        'Rosanna Eleanor Mabel Amelia Charlotte Harriet Caroline Matilda Judith Joanna Emma Laura Lena Jessie '
        'Eveline Edith Alicia Marcella Debby Polly Betty Elsie Florence Dorothy Rebecca Clara Gertrude Eileen '
        'Norah',
        'Patrick Michael John Daniel Timothy Cornelius Dennis Thomas Jeremiah Owen James William Edward '
        'Bartholomew Florence Terence Hugh Martin Peter Francis Joseph Bernard Matthew Laurence Christopher '
        'Andrew Charles Edmund Richard Maurice Thady Myles Felix Eugene Denis Darby Dermot Jerome Garrett '
        'Gerald Henry Luke Mark Morgan Nicholas Philip Robert Roger Stephen Simon Malachy Murtagh Neil Mortimer '
        'Anthony Ambrose Alexander Arthur George Paul Pierce Redmond Raymond Ulick Brian Manus Barney Dominick '
        'Colman Godfrey Oliver Samuel Sylvester Theobald Valentine Vincent Walter Randal Albert Alfred Austin '
        'Benjamin Frederick Louis Lewis Ellis David Jasper Roderick Matthias Malachi Constantine Moses Harry '
        'Frank Ned Mick Dan Tim Jerry',
        '',
        "Sullivan Murphy O'Brien Kelly Driscoll Connell Mahony Callaghan Doyle Byrne Flynn Brennan Ryan Walsh "
        "O'Neill Kennedy McCarthy Donovan Leary Regan Kavanagh Fitzgerald Burke Hayes Carroll Nolan Keane Quinn "
        "Daly Healy Kearney Moriarty Fitzpatrick Hogan Connolly Collins O'Connor Lynch Murray Dunne Brady Power "
        "Dempsey Farrell Gallagher Doherty Boyle Maguire McLoughlin Kane Devlin Kenny Reilly Clarke Keogh "
        "Whelan Foley Hurley Mullins O'Donnell Rooney McDonnell Flanagan Duggan Hickey Coleman Cullen Barry "
        "Ahern Barrett Butler Costello Cronin Crowley Cummins Curran Delaney Dillon Dolan Donnelly Doran Duffy "
        "Egan Fahy Finnegan Gleeson Griffin Hanlon Hennessy Higgins Horgan Keating Lawlor Lennon Lyons "
        "McCormack McGrath McKenna McMahon Madden"),
    'scottish': group(
        'Jessie Isabella Christina Janet Agnes Margaret Euphemia Marion Grace Helen Mary Elizabeth Ann Jane '
        'Catherine Elspeth Barbara Williamina Jemima Robina Georgina Jean Flora Annie Effie Rachel Sarah Bella '
        'Davina Jacobina Thomasina Marjory Christian Betty Peggy Kirsty Lilias Alison Henrietta Wilhelmina '
        'Johanna Nancy Katherine Ellen Eliza Joan Annabella Clementina Murdina Dolina Donalda Hughina Kate '
        'Morag Mairi Maggie Lizzie Nellie Minnie Ina Sophia Joanna Martha Susan Mina Lucy Louisa Charlotte '
        'Caroline Julia Frances Matilda Emily Alice Eleanor Harriet Hannah Esther Ishbel Rhoda Lily Mabel '
        'Violet Edith Ada Emma Florence Alexandrina Mary_Ann Katie Elsie Maud Ethel Rose Nora Beatrice Muriel '
        'Lilian Dora Amelia',
        'Alexander Duncan Hugh Angus Donald Archibald Malcolm Robert Andrew David John James William Thomas '
        'George Peter Colin Neil Kenneth Allan Ewan Lachlan Murdo Roderick Dugald Walter Gilbert Adam Charles '
        'Henry Daniel Ninian Hector Norman Gavin Matthew Fergus Farquhar Finlay Ronald Ranald Torquil Alister '
        'Calum Aeneas Sandy Magnus Mungo Quintin Innes Joseph Samuel Richard Edward Francis Frederick Arthur '
        'Albert Alfred Harry Ernest Herbert Patrick Michael Stephen Benjamin Isaac Jonathan Nathaniel Ebenezer '
        'Gideon Lewis Laurence Edwin Sidney Percy Douglas Leslie Graham Gordon Martin Philip Jacob Moses Ralph '
        'Simon Dougal Ivor Ian Hamish Alastair Somerled Gregor Bruce Crawford Murdoch Evan Willie Tom Archie',
        '',
        'Macdonald Campbell Stewart Robertson Murray Fraser Grant Reid Cameron Ross Henderson Paterson '
        'Mackenzie Mackay Macleod Maclean Johnston Scott Anderson Smith Brown Thomson Wilson Kerr Hamilton '
        'Mitchell Watson Gordon Morrison Ferguson Sinclair Munro Douglas Cunningham Kennedy Macgregor '
        'Mackintosh Maclachlan Macpherson Macmillan Macintyre Mackinnon Macrae Macaulay Macfarlane Macneil '
        'Macnab Mackie Macdougall Black White Young Miller Clark Taylor Martin Walker Wallace Bell Duncan Craig '
        'Allan Lindsay Graham Russell Hunter Shaw Ritchie Simpson Watt Boyd Logan Hay Burns Crawford Dunbar '
        'Lamont Laing Baird Bruce Buchanan Chisholm Drummond Erskine Forbes Gillespie Gunn Innes Keith Leslie '
        'Lockhart Maxwell Moffat Napier Ogilvie Rankin Rae Rutherford Sutherland Wylie'),
    'jewish': group(
        'Rachel Leah Rebecca Esther Hannah Miriam Rosa Fanny Sophia Betsy Sarah Rose Kate Annie Dinah Judith '
        'Bella Golda Rivka Chaya Malka Feiga Deborah Rosetta Kitty Amelia Julia Matilda Phoebe Bertha Clara '
        'Minnie Lily Gertrude Rosalie Augusta Caroline Charlotte Celia Dora Eva Emma Flora Florence Frances '
        'Henrietta Ida Isabella Jane Jessie Lena Louisa Lydia Maria Marian Martha Millie Paulina Polly '
        'Priscilla Rosalind Ruth Sadie Selina Susannah Theresa Zillah Ada Abigail Adelaide Alice Elizabeth '
        'Ellen Emily Freda Gussie Rosie Etta Yetta Zelda Sheindel Perel Pessie Gittel Hinda Mindel Bryna Shifra '
        'Sima Fruma Raizel Basha Bluma Breina Ettie Becky Simmy Zipporah Sophie Naomi',
        'Isaac Samuel Moses Solomon Abraham Joseph Lewis Nathan Benjamin Hyman David Jacob Aaron Mark Henry '
        'Israel Barnett Woolf Lazarus Morris Myer Simon Michael Emanuel Asher Phineas Mordecai Harris Louis '
        'Jonas Philip Alfred Reuben Joel Elias Daniel Edward Ephraim Ezekiel Frederick George Gabriel Isidore '
        'Jonathan Joshua Judah Julius Leon Leopold Levi Lionel Marcus Maurice Max Nathaniel Noah Raphael Samson '
        'Saul Sidney Victor Zachariah Albert Alexander Arthur Bernard Charles Ernest Harry Herbert Lawrence '
        'Leonard Montague Percy Ralph Edgar Augustus Ellis Elkan Gershon Hillel Jonah Kalman Lipman Naphtali '
        'Tobias Eleazar Gideon Chaim Mendel Hirsch Leib Selig Fishel Zalman Herschel Nachman Shmuel Barnet '
        'Sampson',
        '',
        'Cohen Levy Isaacs Jacobs Hart Moss Abrahams Myers Solomon Lazarus Goldsmith Mendoza Samuels Davis '
        'Harris Lyons Phillips Marks Joseph Nathan Levi Moses Benjamin Franks Barnett Rosenberg Goldstein '
        'Lipman Woolf Emanuel Henriques Schwartz Silverman Gompertz Aarons Adler Alexander Baron Bernstein '
        'Montefiore Mocatta Sassoon Belisario Lindo Lopes Nunes Pinto Sebag Rothschild Goldsmid Salomons '
        'Montagu Samuel Franklin Waley Elias Feldman Frankel Freedman Friedman Gold Goldberg Goldman Greenberg '
        'Gross Hyams Isaacson Israel Jacobson Josephs Kaplan Katz Klein Landau Levene Levin Levine Levinson '
        'Lewin Michaels Mendelsohn Oppenheim Polak Rosen Rosenthal Rubinstein Sachs Salaman Simmons Simons '
        'Stern Wolff Wolfson Zangwill Gluckstein Salmon Gollancz Hirsch Asher Davids'),
    'italian': group(
        'Maria Giuseppina Rosa Teresa Angela Lucia Carmela Anna Caterina Francesca Margherita Luigia Antonia '
        'Giovanna Filomena Assunta Carolina Elisabetta Domenica Concetta Annunziata Raffaella Vincenza '
        'Michelina Angiolina Pasqualina Marianna Clementina Giulia Elena Clotilde Adelaide Agnese Luisa '
        'Angelina Maddalena Rosina Rosaria Rachele Nicoletta Benedetta Lucrezia Cristina Laura Paola Gaetana '
        'Grazia Immacolata Marta Natalina Orsola Palmira Pasqua Santa Serafina Stella Virginia Vittoria Amalia '
        'Adele Albina Beatrice Bianca Camilla Candida Cecilia Celeste Chiara Costanza Emilia Erminia Eugenia '
        'Fortunata Gemma Gilda Giacinta Ida Ines Irene Isabella Italia Letizia Lina Livia Marcella Matilde '
        'Olimpia Ottavia Pia Pierina Regina Rita Rosalia Santina Silvia Sofia Ersilia Giuditta Ester Elvira',
        'Giuseppe Antonio Giovanni Luigi Pietro Carlo Domenico Francesco Angelo Michele Vincenzo Pasquale '
        'Lorenzo Andrea Battista Giacomo Paolo Stefano Raffaele Alfonso Gaetano Salvatore Filippo Bartolomeo '
        'Enrico Achille Ercole Cesare Agostino Natale Emilio Federico Vittorio Alessandro Anselmo Arturo '
        'Augusto Benedetto Bernardo Biagio Carmine Cristoforo Davide Ernesto Ettore Eugenio Felice Ferdinando '
        'Fortunato Gabriele Gennaro Gerardo Giacinto Gioacchino Giulio Guglielmo Ignazio Leonardo Leopoldo '
        'Lodovico Luciano Marco Mario Martino Matteo Nicola Ottavio Pellegrino Primo Riccardo Roberto Rocco '
        'Romolo Sebastiano Secondo Silvio Simone Tommaso Ugo Umberto Valentino Vito Alberto Amedeo Attilio '
        'Bruno Celestino Cosimo Costantino Edoardo Egidio Emanuele Faustino Fedele Giorgio Girolamo Giuliano '
        'Guido Isidoro Lazzaro',
        '',
        'Ricci Bianchi Gatti Ferrari Costa Ortelli Gazzi Negretti Zambra Pagliai Rossi Romano Russo Lombardi '
        'Colombo Bertolini Mariani Conti Rinaldi Fontana Moretti Bruno Marino Galli Cavalli Grossi Brunetti '
        'Sartori Mancini Ronchetti Pagani Gianelli Esposito Greco De_Luca Giordano Rizzo Lombardo Barbieri '
        'Fabbri Ferrara Caruso Leone Longo Gentile Martinelli Vitale Serra De_Santis Marchetti Parisi Villa '
        'Conte Ferri Fiore Testa Pellegrini Palumbo Farina Benedetti Bernardi Cattaneo Donati Ferraro Gallo '
        'Guerra Monti Morelli Orlando Pace Riva Santoro Silvestri Valentini Zanetti Cirillo Amato De_Rosa '
        'Messina Basile Bellini Bassi Neri Carbone Grasso Pagano Marini Mazza Rossetti Sorrentino Tedesco '
        'Biondi Martini Ruggiero Pozzi Fumagalli Brambilla Ricciardi Coppola Valente'),
    'west-riding': group(
        'Hannah Martha Sarah Ann Mary Ellen Elizabeth Alice Emma Ruth Phoebe Mercy Esther Annie Ada Polly Edith '
        'Lizzie Jane Harriet Betty Nancy Grace Charlotte Susannah Rebecca Rachel Leah Miriam Keziah Rhoda '
        'Deborah Lydia Priscilla Tabitha Dinah Jemima Judith Naomi Abigail Patience Charity Prudence Emily '
        'Clara Florence Ethel Lilian Gertrude Maud Beatrice Mabel Elsie Nellie Minnie Gladys Amy Lucy Sally '
        'Kate Jessie Margaret Isabella Eliza Louisa Caroline Frances Fanny Selina Matilda Bertha Agnes Hilda '
        'Lily Rose Violet Ivy Daisy May Dorothy Sophia Catherine Hester Julia Edna Doris Mary_Ann Sarah_Ann '
        'Susan Betsy Bessie Zillah Lavinia Hephzibah Emmeline Clarissa Jessica Amelia Henrietta Rosa',
        'John William Joseph James Thomas George Samuel Benjamin Abraham Jonas Joshua Eli Fred Harold Albert '
        'Walter Tom Ned Henry Charles Edward Richard Robert Frank Harry Arthur Ernest Herbert Frederick Alfred '
        'Edwin Edgar Wilfred Willie Percy Sam Ben Jim Isaac Jacob Joel Josiah Jabez Enoch Elijah Elisha Ezra '
        'Amos Job Levi Reuben Seth Simeon Squire Hiram Moses Aaron Nathan Nathaniel Jonathan Matthew Mark Luke '
        'Michael David Daniel Abel Absalom Caleb Gideon Obadiah Zachariah Jeremiah Noah Asa Titus Uriah Edmund '
        'Lewis Clement Ellis Stanley Leonard Norman Cyril Clifford Allen Ambrose Jack Jesse Nehemiah Joe Dick '
        'Sidney Hubert Lister Ephraim Hezekiah Gilbert Oliver',
        '',
        'Sugden Ackroyd Holroyd Greenwood Sutcliffe Crowther Haigh Hirst Barraclough Firth Ramsden Wadsworth '
        'Butterworth Normanton Brearley Hinchliffe Pickles Shackleton Mitchell Booth Lumb Priestley Wormald '
        'Ingham Rushworth Dobson Sykes Lockwood Armitage Beaumont Brook Broadbent Hargreaves Holdsworth '
        'Illingworth Jowett Kershaw Lister Midgley Mortimer Naylor Oldroyd Pollard Redman Riley Robertshaw '
        'Schofield Senior Shaw Stansfield Sunderland Swift Thackray Townend Walshaw Whiteley Wilkinson Asquith '
        'Atkinson Bairstow Barker Bentley Binns Blackburn Boothroyd Bottomley Bradley Briggs Calvert Clayton '
        'Cockcroft Crabtree Dawson Denison Dyson Earnshaw Ellis Feather Gaukroger Gledhill Greaves Hainsworth '
        'Hartley Heaton Helliwell Hey Holmes Horsfall Hudson Jagger Kitson Laycock Lee Marsden Moorhouse Mellor '
        'Nutter Ogden Pearson Pickersgill'),
}

MEDIEVAL = {
    # source: feminine additions from "Feminine Given Names in A Dictionary of English Surnames", names attested before
    #   1250 (s-gabriel.org/names/talan/reaney/index_early1,2,5), and "Women's Given Names from Early 13th Century
    #   England" (s-gabriel.org/names/talan/eng13/eng13f.html); masculine and family names from general knowledge (estimate).
    'norman': group(
        'Alice Isabel Matilda Joan Margery Agnes Emma Juliana Petronilla Avice Cecily Rohese Sybil Beatrice '
        'Eleanor Mabel Margaret Hawise Amice Constance Adeliza Ela Lucy Eva Basilia Maud Gundreda Aline '
        'Clemence Nichola Idonea Adela Aveline Agatha Amabel Christiana Denise Dionisia Ermengarde Euphemia '
        'Felicia Ida Laura Letitia Muriel Olive Philippa Rose Sabina Theophania Adelina Annora Ascelina Clarice '
        'Emeline Ermentrude Eustacia Gunnora Hersent Juetta Katherine Lescelina Millicent Mirabel Sarra '
        'Scholastica Tiffany Ismay Yolande Blanche Christina Rosamund Joanna Lauretta Isabella Albreda Galiena '
        'Elizabeth Annabel Osanna Lucia Pavia Regina Richolda Sidony Clara Adelaide Anastasia Barbara Douce '
        'Hodierna Odelina Orabel Pleasance Camilla Engelise Richild',
        'William Robert Richard Ralph Hugh Walter Geoffrey Roger Gilbert Henry Simon Thomas Nicholas Baldwin '
        'Reginald Guy Hamo Ranulf Eustace Fulk Alan Bertram Payn Roland Stephen Peter Philip Humphrey Miles '
        'Waleran Osbert Aubrey Amaury Anselm Arnulf Bartholomew Bernard Brian Drogo Ingram Everard Gerard '
        'Gervase Godfrey Herbert Hubert Ivo Jocelyn Lambert Maurice Matthew Odo Osbern Theobald Thurstan Warin '
        'Walkelin Adam Alexander Arnold Baldric Bertrand Hervey Ilbert Jordan Laurence Mauger Nigel Osmund '
        'Picot Savaric Serlo Tancred Urse Samson Saer Eudo Warner Engelard Lanfranc John Edmund Edward Gerald '
        'Hamelin Joscelin Andrew Michael Amfrid Unfrid Turold Gunfrid Wigan Rainald Fulcher Ernulf Roscelin '
        'Neel Fulbert Ernald',
        '',
        "de_Clare de_Lacy Mortimer Peverel Basset Beauchamp Mandeville Giffard Clifford Malet Ferrers Talbot "
        "de_Vere Bigod Percy Mowbray de_Warenne Fitzalan Courtenay Neville Despenser Grey de_Bohun Marshal "
        "de_Montfort Lovel Saint_John Bardolf Devereux Paynel de_Beaumont de_Braose de_Courcy de_Quincy de_Ros "
        "de_Say de_Stuteville de_Tosny de_Vesci de_Verdun de_Valence de_Lucy de_Burgh de_Brus Balliol de_Lisle "
        "Clinton Darcy Fiennes Gournay Harcourt Maltravers Montagu Montgomery Mohun Pipard Poynings Saint_Clair "
        "Saint_Leger Sackville Scrope Segrave Somery Stafford Tracy Umfraville Vavasour Venables Zouche "
        "Cantilupe Chaworth Corbet Crevecoeur Damory Engaine Fitzwalter Fitzwarin Fitzhugh Fitzwilliam "
        "Fitzherbert Fitzgerald Fitzosbern Furnival Glanville Gresley Hastings Hussey le_Strange Longchamp "
        "Marmion Mauduit Morville Pantulf Poyntz Raleigh Seymour Turberville Valoines Vipont d'Aubigny"),
    # source: feminine additions from "Women's Given Names from Early 13th Century England" (s-gabriel.org/names/talan/
    #   eng13/eng13f.html) and "Yorkshire Feminine Names from 1379" (s-gabriel.org/names/talan/yorkshire/yorkf.html);
    #   the rest from general knowledge (estimate).
    'english': group(
        'Agnes Alice Maud Edith Joan Emma Margery Christina Godiva Elfrida Wymarc Ellen Annot Tibb Mariot '
        'Isabel Cecily Juliana Matilda Margaret Katherine Lettice Amice Avice Sibyl Mabel Hawise Denise Felicia '
        'Rose Lucy Beatrice Gunnild Idonea Eva Alison Amabel Christian Clarice Constance Eleanor Goda Hilda '
        'Mildred Audrey Millicent Muriel Nicola Olive Parnel Philippa Sabina Susanna Elizabeth Anne Gillian '
        'Malkin Emmot Jenet Ida Rosamund Sarra Dulcia Agatha Marion Thomasina Benedicta Edeline Helen Aldith '
        'Edeva Leofrun Wulfrun Goldburga Thora Sigrid Margot Joanna Laura Ellota Magota Euphemia Annabel Mary '
        'Amy Petronilla Alviva Estrild Ragenild Aveline Gunnora Osanna Runild Scholastica Godeleva Aldiva '
        'Eunice',
        'John Thomas Adam Walter Wat Hob Robin Peter Simkin Edwin Godric Alfred Osric Wulfric Tom Dickon '
        'William Richard Robert Henry Roger Hugh Nicholas Ralph Geoffrey Gilbert Stephen Alan Simon Philip '
        'Laurence Jordan Elias Osbert Hamo Ranulf Gervase Martin Alexander Andrew Bartholomew Benedict Edmund '
        'Edward Edric Edgar Godwin Herbert Hubert Ivo Jocelin Lambert Matthew Maurice Michael Miles Nigel '
        'Oliver Osmund Piers Silvester Theobald Thurstan Warin Wulfstan Leofric Leofwine Aylwin Cuthbert '
        'Dunstan Oswald Siward Thurkill Colin Bennet Clement Denis Fulk Giles Gregory Guy Humphrey James Lucas '
        'Mark Samson Warner Baldwin Anselm Absalom Austin Christopher Daniel David Everard Ingram Jankin Jenkin '
        'Hick Hodge',
        '',
        'Atwood Miller Smith Baker Fletcher Carter Thatcher Webster Brewer Cooper Turner Shepherd Fisher Wright '
        'Chapman Mason Ward Fowler Gardner Bowyer Cook Taylor Skinner Tanner Dyer Hunt Reeve Glover Webb Walker '
        'Spencer Palmer Fuller Barker Attwell Bywater Underwood Archer Bailey Barber Bell Bishop Bond Bowman '
        'Brown Butcher Butler Carpenter Chandler Clark Collier Draper Freeman Godwin Granger Green Hayward Hill '
        'Hooper Kemp Knight Lambert Lane Lister Marshall Mercer Mills Naylor Page Parker Payne Plowman Potter '
        'Reed Roper Rowe Sadler Salter Sawyer Saunders Sexton Shearer Slater Spicer Stone Swift Thacker Tiler '
        'Tucker Wainwright Warner Weaver Wheeler White Wood Woodward Young Abbot Atwater Fairfax'),
    # source: given names from "13th Century Welsh Names" (s-gabriel.org/names/tangwystyl/welsh13/), "Given Names from
    #   the Ystrad Marchell Charters 1176-1283" (s-gabriel.org/names/constanza/ystradmarchell-given.html) and "Women's
    #   Names in the First Half of 16th Century Wales" (s-gabriel.org/names/tangwystyl/welshWomen16/given.html);
    #   patronymic family names built from those given names (estimate).
    'welsh': group(
        'Gwen Angharad Nest Gwenllian Morfudd Eluned Tangwystl Lleucu Efa Generys Gwladus Dyddgu Mallt Margred '
        'Annes Gwerful Myfanwy Gwenhwyfar Elen Senena Ales Hunydd Gwenfrewi Mabli Iwerydd Cristin Euron Jonet '
        'Lowri Catrin Elliw Joan Elizabeth Eleanor Mary Rose Dorothy Juliana Amy Cecilia Tacy Emma Joyce '
        'Gwledyr Morfyl Erdudfyl Gwerydd Madrun Perweur Genilles Geneth Gwir Mabel Millicent Siwan Hawys '
        'Eurgain Erddylad Gaenor Gwenonwy Gwenddydd Dwynwen Isabel Alson Ellen Agnes Mererid Sioned',
        'Dafydd Rhys Owain Gruffudd Madog Iorwerth Llywelyn Hywel Ieuan Einion Cadwgan Maredudd Cynan Tudur '
        'Goronwy Ithel Bleddyn Rhodri Cadwaladr Morgan Trahaearn Ednyfed Phylip Gwilym Llywarch Meurig Cynwrig '
        'Heilyn Cadell Rhirid Seisyll Caradog Elidir Iago Adda Tegwared Gwion Madyn Griffri Ednowain Cydifor '
        'Iocyn Cyfnerth Morfran Deheuwynt Gwasdewi Llygad Idnerth Peredur Sulien Iolo Gwalchmai Cynddelw '
        'Deiniol Gwallter Gwgon Hwfa Ieuaf Maelgwn Meilyr Moreiddig Rhydderch Rhun Cadfan Cadwallon Ifor Morys '
        'Rheinallt Rhisiart Siencyn Hopcyn Tomos Lewys Rhiwallon Gwrgenau Bledri Cuhelyn Tudwal Iddon Ynyr '
        'Cynfyn Gwyn Gwenwynwyn Guto Gutun Deio Sion Wiliam',
        '',
        'ap_Rhys ap_Owain ferch_Madog Gwyn Llwyd Vychan Goch Ddu ap_Dafydd ap_Gruffudd ap_Ieuan ap_Hywel '
        'ap_Madog ap_Llywelyn ap_Einion ap_Iorwerth ap_Maredudd ap_Tudur ap_Cynwrig ap_Goronwy ap_Ithel '
        'ferch_Dafydd ferch_Rhys ferch_Gruffudd ferch_Ieuan ferch_Hywel Moel Bach Hir Crach Gethin ap_Gwilym '
        'ap_Rhodri ap_Cadwgan ap_Bleddyn ap_Cynan ap_Llywarch ap_Meurig ap_Morgan ap_Phylip ap_Adda ap_Iago '
        'ap_Trahaearn ap_Ednyfed ap_Caradog ap_Gwyn ap_Rhun ap_Rhydderch ap_Ifor ap_Morys ap_Hopcyn ap_Siencyn '
        'ap_Rhisiart ap_Meilyr ap_Gwgon ap_Cadwallon ap_Tudwal ap_Heilyn ap_Cadell ap_Seisyll ap_Elidir ap_Iolo '
        'ap_Deio ap_Gutun ap_Tomos ap_Ieuaf ap_Cadfan ap_Ynyr ap_Iddon ap_Bledri ferch_Owain ferch_Llywelyn '
        'ferch_Einion ferch_Iorwerth ferch_Maredudd ferch_Tudur ferch_Cynwrig ferch_Goronwy ferch_Ithel '
        'ferch_Gwilym ferch_Morgan ferch_Rhodri ferch_Cadwgan ferch_Bleddyn ferch_Llywarch ferch_Meurig '
        'ferch_Phylip ferch_Adda Gam Sais Gloff Wyddel Tew Ieuanc Hael Mawr Gryg Benfras Teg Hen'),
}

FRONTIER = {
    'american': group(
        'Mary Sarah Martha Hattie Lizzie Nancy Lucinda Mattie Emma Ida Josephine Belle Clara Laura Minnie Sadie '
        'Cora Nellie Pearl Effie Elizabeth Anna Margaret Ellen Catherine Jane Susan Rebecca Rachel Rhoda Lydia '
        'Harriet Ann Eliza Louisa Julia Frances Fannie Lucy Alice Annie Bessie Jennie Maggie Lula Lottie Ella '
        'Ada Flora Florence Etta Nettie Rosa Lillie Mollie Callie Dora Della Eva Grace Hannah Abigail Amanda '
        'Matilda Malinda Melissa Delilah Charlotte Caroline Lavinia Mahala Permelia Parthenia Elvira Virginia '
        'Georgia Vinnie Viola Kate Cynthia Sallie Polly Susannah Priscilla Phoebe Ruth Esther Agnes Augusta '
        'Adeline Orpha Olive Lena Almira Emeline Hester Lettie Hettie Ollie Ophelia',
        'John James William George Charles Henry Thomas Samuel Joseph Wyatt Jesse Amos Silas Lafayette Elijah '
        'Ezra Calvin Ben Lem Jim Robert Edward David Daniel Andrew Benjamin Isaac Jacob Joshua Nathan Nathaniel '
        'Levi Lewis Marion Martin Walter Frank Harry Albert Alfred Edwin Frederick Richard Francis Hiram Asa '
        'Abner Absalom Alonzo Alvin Ambrose Archibald Augustus Cyrus Clay Eli Elisha Emmett Enoch Ephraim '
        'Erastus Ethan Felix Gideon Granville Harrison Harvey Hezekiah Horace Isom Jasper Jefferson Jeremiah '
        'Jonas Josiah Leander Lemuel Lorenzo Lucius Luther Marcus Micajah Milton Moses Newton Noah Oliver '
        'Orville Oscar Perry Philip Reuben Rufus Sampson Seth Stephen Sterling Thaddeus Theodore Ulysses',
        '',
        'Clanton Hughes Bradshaw Pruitt Tolliver Haskell Whitfield Gentry Burris Coffey Rutledge Spence Dunlap '
        'Crenshaw Harlan Fenton Rhodes McKinney Baird Bascom Puckett Yancey Smith Johnson Williams Brown Jones '
        'Davis Miller Wilson Moore Taylor Anderson Thomas Jackson White Harris Martin Thompson Allen Young '
        'Walker Wright Hill Scott Green Adams Baker Nelson Carter Mitchell Campbell Roberts Parker Evans Turner '
        'Collins Cook Bell Ward Cox Howard Brooks Gray Reed Price Barnes Ross Henderson Coleman Jenkins Perry '
        'Powell Long Patterson Foster Russell Griffin Hayes Ford Hamilton Graham Wallace Woods Cole West Owens '
        'Reynolds Fisher Ellis Harrison Gibson Marshall Wells Simpson Stevens Tucker Porter Hunter Hicks'),
    'mexican': group(
        'Maria Josefa Refugio Guadalupe Dolores Manuela Juana Soledad Petra Ramona Trinidad Carmen Francisca '
        'Antonia Rosa Teresa Luz Paula Rafaela Concepcion Encarnacion Ignacia Jesusa Gertrudis Isabel Ana Rita '
        'Lugarda Mercedes Altagracia Marcelina Feliciana Leonor Victoria Margarita Juliana Luisa Micaela Marta '
        'Brigida Catalina Clara Barbara Andrea Josefina Eulalia Gregoria Dominga Tomasa Agustina Rosalia Susana '
        'Ines Apolonia Benita Candelaria Casimira Crescencia Damiana Estefana Eusebia Faustina Felipa '
        'Florentina Gabriela Inocencia Jacinta Leocadia Lorenza Lucia Macaria Marcela Martina Matilde Natividad '
        'Nicolasa Pascuala Paulina Pilar Prudencia Rosario Sabina Serafina Simona Valentina Vicenta Elena '
        'Eugenia Beatriz Anastasia Asuncion Candida Celestina Cipriana Delfina Dorotea Epifania Fermina Hilaria '
        'Maria_Antonia',
        'Jose Juan Manuel Francisco Jesus Ignacio Pedro Ramon Antonio Santiago Esteban Rafael Miguel Jose_Maria '
        'Luis Tomas Joaquin Felipe Andres Agustin Vicente Cristobal Julian Bernardo Teodoro Marcos Nicolas '
        'Mariano Lorenzo Gregorio Ysidro Tiburcio Atanacio Bartolo Anastasio Diego Alejandro Blas Benito '
        'Bonifacio Calixto Candelario Carlos Cayetano Cipriano Dionisio Domingo Eusebio Eugenio Faustino '
        'Feliciano Felix Fernando Gabriel Hilario Jacinto Jeronimo Leandro Lucas Marcelino Martin Matias '
        'Melquiades Pablo Pascual Policarpo Rosendo Salvador Santos Saturnino Sebastian Simon Valentin Ventura '
        'Victoriano Zeferino Apolonio Aniceto Ambrosio Abundio Bernabe Crecencio Desiderio Eleuterio Epifanio '
        'Estanislao Eulogio Fermin Gervasio Hermenegildo Jose_Antonio Jose_Manuel Juan_de_Dios Justo Leonardo '
        'Macario Modesto Narciso Patricio Prudencio',
        '',
        'Romero Elias Ochoa Pacheco Ortiz Telles Leon Aguirre Robles Samaniego Contreras Salazar Montoya Garcia '
        'Martinez Lopez Sanchez Chavez Vigil Lucero Baca Sandoval Archuleta Valdez Gallegos Armijo Otero Luna '
        'Sena Trujillo Gonzales Duran Moreno Estrada Carrillo Hernandez Perez Rodriguez Ramirez Torres Flores '
        'Rivera Gomez Diaz Morales Reyes Cruz Gutierrez Ramos Mendoza Ruiz Alvarez Castillo Jimenez Vargas '
        'Herrera Medina Aguilar Vega Castro Delgado Padilla Apodaca Arguello Bustamante Cordova Espinosa '
        'Fernandez Gurule Jaramillo Maestas Mondragon Olguin Ortega Quintana Rael Salas Serna Silva Tafoya '
        'Tapia Ulibarri Valencia Velasquez Zamora Abeyta Anaya Atencio Benavides Cisneros Esquibel Galindo '
        'Lovato Madrid Manzanares Molina Montano Muniz Nunez Rivas'),
    'cornish': group(
        'Jenefer Mary Elizabeth Grace Thomasine Loveday Jane Kitty Ann Mary_Ann Honour Philippa Wilmot Tamsin '
        'Patience Prudence Jenny Emily Eliza Catherine Susan Martha Charity Mercy Sarah Hannah Ellen Harriet '
        'Emma Bessie Annie Johanna Alice Agnes Dorcas Dorothy Joan Joanna Keziah Lavinia Lydia Margery Margaret '
        'Maria Christian Constance Damaris Eleanor Gertrude Isabella Julia Louisa Lucy Nancy Ruth Rebecca '
        'Selina Sophia Susanna Tryphena Tabitha Temperance Ursula Zenobia Blanche Frances Fanny Rosina Amelia '
        'Ada Caroline Charlotte Clara Edith Elsie Eva Florence Jessie Kate Laura Lilian Mabel Matilda Minnie '
        'Nellie Rachel Rhoda Thirza Jemima Mary_Jane Avis Esther Phillis Hephzibah Loveday_Ann Elizabeth_Ann '
        'Grace_Ann Emily_Jane Lily Henrietta',
        'John Richard William Nicholas Josiah Hart Jabez Thomas Samuel Edward James Henry Joseph George Peter '
        'Stephen Francis Matthew Philip Charles Simon Benjamin Joel Elisha Ezekiel Digory Hannibal Mark Michael '
        'Paul Abraham Jacob Silas Walter Anthony Arthur Alfred Albert Caleb Daniel David Edwin Enoch Ephraim '
        'Frederick Hezekiah Humphrey Isaac Jonathan Joshua Jethro Levi Lewis Martin Moses Nathaniel Noah '
        'Obadiah Oliver Reuben Robert Ralph Shadrach Theophilus Tobias Uriah Absalom Amos Archelaus Bennet '
        'Christopher Clement Edmund Ebenezer Eli Elijah Frank Harry Herbert Hugh Jasper Jonas Justinian '
        'Nehemiah Pentecost Sampson Simeon Solomon Tristram Vivian Zebedee Zacharias Jenkin Ezra Hender Malachi '
        'Ambrose Nathan Gilbert Andrew',
        '',
        'Trevithick Penrose Polglase Tregear Pascoe Trelawny Nankivell Rowe Bolitho Pengelly Tremayne Chenoweth '
        'Trevena Trethewey Tregonning Penhaligon Pendarves Jory Jago Hocking Hosking Williams Rule Nance Oates '
        'Tonkin Uren Rodda Curnow Trewartha Kitto Polkinghorne Spargo Dunstan Angove Bawden Berryman Bray Carne '
        'Chegwidden Couch Cundy Dingle Eddy Glasson Gilbert Hambly Harvey Hicks Hoskin Jenkin Kemp Lander '
        'Lanyon Laity Mitchell Nancarrow Opie Paull Pearce Penberthy Pender Pentreath Pengilly Phillips Prowse '
        'Quick Retallack Roberts Sampson Stephens Teague Thomas Treloar Tregenza Tremewan Trengove Trewin '
        'Trezise Tyack Varcoe Vosper Wearne Woolcock Bennetts Gluyas Grenfell Jewell Keast Kneebone Lobb Martyn '
        'Moyle Nicholls Olver Penhale Rosevear Sobey Symons Tamblyn'),
    'irish': group(
        'Bridget Mary Margaret Annie Kate Nora Ellen Catherine Johanna Honora Julia Ann Mary_Ann Elizabeth '
        'Delia Winifred Sarah Hannah Alice Teresa Agnes Rose Jane Eliza Maggie Lizzie Nellie Bessie Abbie Susan '
        'Josephine Celia Peggy Molly Katie Minnie Ellie Jenny Nancy Sally Biddy Kathleen Frances Fanny Isabella '
        'Sophia Martha Maria Cecilia Monica Anastasia Deborah Penelope Una Grace Helena Helen Esther Emily '
        'Louisa Margery Barbara Lucy Letitia Philomena Bernadette Agatha Rosanna Eleanor Mabel Amelia Charlotte '
        'Harriet Caroline Matilda Judith Joanna Emma Laura Lena Jessie Edith Alicia Marcella Polly Betty '
        'Florence Dorothy Rebecca Clara Gertrude Eileen Kitty Christina Sabina Abina Mamie Nora_Ann Ella '
        'Theresa',
        'Patrick Michael Dennis Timothy Cornelius Owen Daniel John James Thomas William Edward Bartholomew '
        'Jeremiah Terence Hugh Martin Peter Francis Joseph Bernard Matthew Laurence Andrew Charles Richard '
        'Maurice Myles Felix Edmund Thady Barney Eugene Denis Darby Dermot Jerome Garrett Gerald Henry Luke '
        'Mark Morgan Nicholas Philip Robert Roger Stephen Simon Malachy Murtagh Neil Mortimer Anthony Ambrose '
        'Alexander Arthur George Paul Pierce Redmond Raymond Ulick Brian Manus Dominick Colman Godfrey Oliver '
        'Samuel Sylvester Theobald Valentine Vincent Walter Randal Albert Alfred Austin Benjamin Frederick '
        'Louis Christopher Lawrence Matthias Constantine Malachi Moses Harry Frank Ned Mick Dan Tim Jerry Larry '
        'Mike Pat Ellis David',
        '',
        "O'Rourke Sweeney Daly Hogan Mahoney Riordan Cassidy Moran Sullivan Murphy O'Brien Kelly Ryan Walsh "
        "Kennedy McCarthy Donovan Burke Fitzgerald Carroll Nolan Quinn Connolly Dwyer Kearney Duffy Lynch "
        "McGrath Shea Hennessy Brady Tobin Collins O'Connor Murray Dunne Power Dempsey Farrell Gallagher "
        "Doherty Boyle Maguire McLoughlin Kane Devlin Kenny Reilly Clarke Keogh Whelan Foley Hurley Mullins "
        "O'Donnell Rooney McDonnell Flanagan Duggan Hickey Coleman Cullen Barry Ahern Barrett Butler Costello "
        "Cronin Crowley Cummins Curran Delaney Dillon Dolan Donnelly Doran Egan Fahy Finnegan Gleeson Griffin "
        "Hanlon Higgins Horgan Keating Lawlor Lennon Lyons McCormack McKenna McMahon Madden Maher Mooney "
        "Mulcahy Mulligan Noonan O'Donoghue O'Keeffe Phelan"),
    'german': group(
        'Anna Katharina Margaretha Elisabeth Louisa Wilhelmina Emma Maria Christina Sophia Barbara Magdalena '
        'Dorothea Friederike Caroline Johanna Bertha Amalia Paulina Rosina Augusta Mathilde Theresa Clara Lina '
        'Minna Ida Helena Henriette Charlotte Frieda Eva Agnes Albertina Babette Cecilia Dora Elise Ella Emilie '
        'Ernestine Franziska Gertrud Hedwig Hermine Josephine Juliana Justine Kunigunde Lena Lisette Lydia '
        'Martha Ottilie Regina Rosalie Sabina Selma Sibylla Susanna Ursula Veronika Walburga Adelheid Agathe '
        'Apollonia Brigitta Elsa Gretchen Hanna Irma Josepha Lotte Lucia Tekla Viktoria Eleonore Gisela Hulda '
        'Irene Klothilde Leonore Meta Olga Rebekka Salome Marie Luise Katharine Margarethe Christine Theresia '
        'Sophie Pauline Louise Friedericke Karoline Annie Mary Lizzie',
        'Johann Friedrich Heinrich Wilhelm Karl August Otto Georg Jakob Philipp Peter Ludwig Christian Adam '
        'Konrad Michael Franz Joseph Hermann Gottlieb Ernst Gustav Martin Andreas Valentin Anton Fritz '
        'Christoph Nikolaus Matthias Adolph Rudolph Albert Balthasar Benedikt Bernhard Daniel David Dietrich '
        'Eduard Emil Erhard Felix Ferdinand Gerhard Gottfried Gottlob Hans Hugo Ignatz Julius Kaspar Leonhard '
        'Leopold Lorenz Lukas Markus Max Moritz Oskar Paul Reinhold Richard Robert Sebastian Simon Stephan '
        'Theodor Thomas Traugott Ulrich Urban Victor Walter Werner Wendelin Wolfgang Xaver Alois Arnold Bruno '
        'Clemens Engelbert Eugen Fridolin Gebhard Hubert Isidor Kilian Lambert Lothar Melchior Oswald Reinhard '
        'Siegfried Theobald Vinzenz Wenzel Albrecht Hieronymus',
        '',
        'Schmidt Becker Vogel Hartmann Kessler Lutz Brunner Weber Zimmermann Mueller Schneider Fischer Meyer '
        'Wagner Schulz Hoffmann Koch Bauer Richter Klein Wolf Schroeder Neumann Schwarz Braun Krueger Hofmann '
        'Lange Werner Krause Meier Lehmann Fuchs Keller Jung Hahn Schubert Vogt Friedrich Scholz Boehm Martin '
        'Schumacher Frank Berger Winkler Roth Beck Lorenz Baumann Franke Albrecht Schuster Simon Ludwig Winter '
        'Kraft Schumann Haas Seidel Heinrich Brandt Kuhn Busch Pohl Horn Arnold Sauer Engel Kaiser Ziegler Graf '
        'Dietrich Herrmann Huber Mayer Schreiber Peters Jaeger Gross Ernst Hess Otto Pfeiffer Ritter Stein '
        'Schaefer Sommer Stahl Thiel Ulrich Voigt Walter Wendt Eckert Gerber Hauser Koenig Metzger Nagel'),
    # source: family additions from Cantonese romanisations in Wikipedia "List of common Chinese surnames"; given-name
    #   additions partly from US National Archives, Prologue 2016 "Broken Blossoms" (archives.gov/publications/prologue/
    #   2016/spring/blossoms.pdf), Nevada Historical Society Quarterly 1975 (epubs.nsla.nv.gov 210777-1975-2Summer)
    #   and Mai Wah Society "Names and Faces" (maiwah.org/?p=202); the rest from general knowledge (estimate).
    'chinese': group(
        'Ah_Ying Mei_Lan Gum_Moy Sing_Toy Lai_Ho Ah_Toy Ah_Moy Ah_Kum Ah_Lan Ah_Yuk Ah_Hoy Ah_Choy Ah_Sue Ah_Ho '
        'Ah_Yoke Ah_Fah Ah_Ngan Ah_Kew Ah_Chun Ah_Lin Gum_Ying Kum_Ho Yut_Ho Yee_Toy Sing_Moy Lin_Moy Kum_Fong '
        'Lai_Ying Fung_Moy Choy_Lin Moy_Ying Yuen_Kum Sue_Kum Ah_Kim Ah_Mui Ah_Oy Ah_Wan Ah_Yee Ah_Ling Ah_Kwai '
        'Ah_Fung Ah_Gum Mei_Ying Kum_Lin Sue_Ying Yuk_Ying Ah_Lai Ah_Mei Ah_Ngoon Ah_Sum Kum_Ying Lin_Ho '
        'Yee_Moy Gwai_Ying Lon_Ying Gim_Gook Gwai_Ha Gow_Sheung Dai_Muey Yow Choy_Ying Sek_Mo Sheung Ling_Fong',
        'Ah_Sam Wing Chung Fook Quong Hop_Kee Sing Ah_Sing Ah_Lee Ah_Kee Ah_Wing Ah_Fong Ah_Chung Ah_Hing '
        'Ah_Quong Ah_Yen Ah_Fook Ah_Louie Ah_Chew Ah_Gow Ah_Hop Ah_Jim Ah_Tom Hong Hing Kee Lung Chew Yuen Bing '
        'Gong Tong Fat Quan Yick Ah_Wah Ah_Ming Ah_Soon Ah_Tong Ah_Chong Ah_Fat Ah_Gee Ah_Bow Ah_Lum Ah_Hong '
        'Ah_Yung Ah_Kim Ah_Wo Ah_Chee Ah_Ying Ah_Foo Wah Ming Chong Soon Foo Look Gee Lum Hop Sang Yee Kim Sun '
        'Ying Hoy Gim Woo Kwong Sam Tung Lai Ah_Ngan Ah_Sang Ah_Look Ah_Tung Chong_Po Quong_Hing Git Lem '
        'Siu_Hon Ngee Mee Mow_Ling Quong_Kee Quie_Sang Jon Wai Fay Pock Wah_Long',
        '',
        'Lee Wong Chan Chin Yee Ng Fong Louie Moy Lum Fung Quan Leong Gin Tom Jue Dea Toy Hom Woo Eng Yuen Hong '
        'Lau Mah Poon Chew Dong Joe Gee Kwong Jung Tsui Suen Ko Cheng Tse Sung Hon Cho Tsang Siu Tin Tung Choi '
        'Tseung Yue To Ngai So Lui Ting Yam Yiu Fu Keung Chui Fan Luk Shek Tai Ha Yau Hau Chau Mang Pak Yim '
        'Tuen Sze Mo Ku Kok Kung Man Heung Chang Chung Cheung Ho Kwan Lai Leung Lo Pang Tam Tang Yip Yu Au Choy '
        'Chow Fok Hui Kam Lam Lew Low Mak Mok'),
}

STORYBOOK = {
    'plain': group(
        'Hester Marigold Tansy Prudence Wilhelmina Bettony Dulcie Maud Bess Ottilie Hazel Posy Clemency Ada '
        'Bryony Winnie Lettice Nell Tibby Gwendolyn Agnes Alice Annie Beatrice Betsy Clara Constance Cicely '
        'Daisy Dora Dorothy Edith Elsie Emily Esther Ethel Eliza Fanny Flora Florence Gertie Grace Hannah '
        'Harriet Henrietta Hilda Honor Ivy Jane Jemima Kate Kitty Lavinia Lily Lizzie Lottie Lucy Mabel Martha '
        'Mary Matilda May Meg Mercy Mildred Millie Minnie Molly Nancy Nettie Olive Patience Peggy Phoebe Polly '
        'Primrose Rose Rosie Ruth Sally Sarah Susan Tabitha Temperance Violet Winifred Bella Bertha Effie Edna '
        'Emma Joan Lettie Marjorie Maisie Mattie Nora Pansy Pearl Poppy',
        'Tobin Bram Hob Wendel Barnaby Ambrose Jory Ned Ferris Osgood Pip Cuthbert Dunstan Rollo Jasper Ezekiel '
        'Lem Horace Bartholomew Wilbur Abel Albert Alfred Amos Arthur Barney Basil Ben Bertie Cecil Clement '
        'Edmund Edgar Edwin Eli Ernest Fred Frederick George Gilbert Giles Harry Herbert Hugh Isaac Jack Jacob '
        'Jethro Joe Jonah Josiah Joseph Lewis Luke Matthew Nat Noah Oliver Oswald Percy Peter Reuben Roger '
        'Rufus Sam Seth Silas Simon Stanley Thomas Tom Walter Wat Will Wilfred Bertram Godfrey Humphrey Toby '
        'Archie Alfie Ezra Enoch Obadiah Septimus Benedict Christopher Daniel Felix Gabriel Henry James John '
        'Martin Nicholas Owen Ralph Robert Rowland Stephen',
        'Robin Kit Jem Frankie',
        'Thistlewood Puddifoot Hobbs Mossley Applegarth Wickham Fennimore Crumb Featherstone Tillbrook Underhay '
        'Oakshott Fairweather Cotton Tanner Pickering Dimmock Hobday Gammage Ottley Brewster Cobb Pennington '
        'Ashby Goodbody Littlejohn Shepherd Weaver Hatcher Merriman Appleby Ashworth Baxter Bellamy Birch '
        'Blackmore Bramley Brook Bunting Butterfield Chandler Cherry Cobbold Cotterill Cowley Crabtree Dale '
        'Dewhurst Drinkwater Dunn Fairclough Farley Fenwick Fletcher Foxley Gardner Garland Goodall Goodwin '
        'Hardcastle Hartley Hawthorn Hayward Heron Hickling Hollins Honeyman Hopkins Kettle Lamb Larkin Lovell '
        'Lowe Meadows Merryweather Middleton Miller Nettleton Norbury Oakley Orchard Partridge Peabody Plumb '
        'Pocock Popplewell Puddephat Rook Rowntree Sadler Sawyer Shipley Sparrow Starling Stubbs Swallow '
        'Thackeray Thatcher Tinker Tomkins'),
}

EDO_JAPAN = {
    # source: general knowledge (estimate: yes)
    'townsfolk': group(
        'Ume Kiku Matsu Take Haru Tsuru Kame Sen Toku Fuku Kin Gin Tome Sato Yoshi Tami Ito Masa Tsune Nobu '
        'Hisa Kiyo Shige Fusa Mitsu Toyo Naka Rin Sayo Chiyo Yasu Mine Kane Tama Taka Teru Tsuya Hana Hatsu Iku '
        'Koto Kuni Michi Miyo Moto Nami Nao Natsu Nui Ritsu Sada Sue Suga Sumi Tatsu Tora Yae Yone Waka Fumi '
        'Kayo Shina Tetsu Aki Iso Ei Fuyu Fude Hide Ichi Ine Iwa Kaku Kana Kiwa Koma Kura Kuma Kume Riyo Sawa '
        'Shika Shizu Some Sono Suzu Tae Tane Toki Tomi Tomo Toshi Tsugi Tsuta Uta Yuki Iyo Kazu Rui Shino',
        'Kichibei Jinbei Rokubei Chobei Kyubei Sobei Zenbei Mohei Kihei Gohei Jiroemon Tasuke Yasubei Kahei '
        'Kichizo Shinsuke Tokubei Ihei Seijiro Manzo Shinzo Tomekichi Kichiemon Gosuke Denbei Sakichi Genshichi '
        'Heisuke Yohei Chojiro Ichibei Kyuzo Hachibei Seibei Rihei Sahei Tahei Hanbei Kanbei Shirobei Magobei '
        'Shinbei Gihei Jubei Chuemon Genemon Jinemon Mataemon Rokuemon Sakuemon Saburoemon Kyusuke Kinsuke '
        'Mansuke Yasuke Chosuke Gensuke Kosuke Densuke Rokusuke Kichisuke Sasuke Sosuke Jusuke Kisuke Yosuke '
        'Zensuke Chokichi Fukukichi Matsukichi Tokichi Seikichi Shinkichi Sankichi Genkichi Kumakichi Kinzo '
        'Rokuzo Sanzo Bunzo Seizo Ginzo Kinjiro Shinjiro Tokujiro Yojiro Kojiro Sojiro Matajiro Kihachi '
        'Hanshichi Shinshichi Tokugoro Kingoro Shingoro Hikogoro Yagoro Yashichi Kyuhachi Tarobei',
        '',
        'Echigoya Mitsui Omiya Iseya Daikokuya Kinokuniya Masuya Yamatoya Kagiya Tsutaya Shirokiya Daimaruya '
        'Matsuzakaya Konoike Izumiya Fujiya Edoya Kazusaya Owariya Mikawaya Tokiwaya Ebisuya Kikuya Sakaiya '
        'Naraya Tamaya Yorozuya Echizenya Surugaya Tachibanaya Yamazakiya Nagasakiya Sumiya Kameya Tsuruya '
        'Toraya Fushimiya Hiranoya Tennojiya Shimaya Settsuya Harimaya Bizenya Bitchuya Bingoya Iyoya Tosaya '
        'Sanukiya Awaya Dewaya Sagamiya Musashiya Hitachiya Shinanoya Minoya Tajimaya Tangoya Inabaya Izumoya '
        'Iwamiya Nagatoya Chikuzenya Higoya Satsumaya Kyoya Osakaya Kashimaya Yodoya Matsuya Takeya Daimonjiya '
        'Ebiya Tawaraya Sumitomo Hishiya Maruya Yamashiroya Kawachiya Tsunokuniya Hyogoya Akashiya Wakasaya '
        'Kagaya Notoya Ecchuya Sadoya Kashiwaya Kiriya Komeya Sakuraya Shimadaya Kogaya Aburaya Sakeya Wataya '
        'Ogiya Fukushimaya Sumiyoshiya Nishimuraya'),
    # source: general knowledge (estimate: yes)
    'samurai': group(
        'Tsuru Kayo Ei Kiku Nui Sachi Iyo Teru Fusa Masa Toshi Yuki Sano Hide Sumi Michi Ritsu Sono Waka Tama '
        'Chika Nao Yoshi Shizu Mine Iso Tomo Sen Kazu Fumi Matsu Taka Ume Take Haru Kame Toku Fuku Kin Gin Tome '
        'Sato Tami Ito Tsune Nobu Hisa Kiyo Shige Mitsu Toyo Naka Rin Sayo Chiyo Yasu Kane Tsuya Hana Hatsu Iku '
        'Koto Kuni Miyo Moto Nami Natsu Sada Sue Suga Tatsu Tora Yae Yone Shina Tetsu Aki Fuyu Fude Ichi Ine '
        'Iwa Kaku Kana Kiwa Koma Kura Kuma Kume Riyo Sawa Shika Some Suzu Tae Tane Toki Tomi Tsugi Tsuta',
        'Kurando Hayato Gunji Denzaemon Kyuzaemon Kazuma Heima Hyogo Tatewaki Gonnosuke Sakon Ukon Jubei Kanbei '
        'Matabei Hikoemon Shozaemon Tadataka Masanobu Yoshinobu Tadashige Shigemasa Kiyomasa Masayuki Yoshitaka '
        'Naoyuki Tomonori Sadanobu Tadakuni Gennai Sanai Heihachiro Kuranosuke Chuzaemon Gonzaemon Heizaemon '
        'Kinzaemon Matazaemon Tarozaemon Hikozaemon Rokuzaemon Kinnosuke Shinnosuke Rinnosuke Ginnosuke '
        'Toranosuke Tatsunosuke Ichinosuke Tonomo Kamon Shume Uneme Mondo Kazue Tanomo Chikara Ukyo Sakyo Hyoe '
        'Danjo Kunai Shikibu Gyobu Jibu Hyobu Kenmotsu Shuri Daizen Takuma Gunpei Hanzo Hanbei Kansuke Saizo '
        'Heikuro Jinnai Tadaaki Masanori Nobuyuki Tadatsugu Kagekatsu Tadanori Masatsugu Kiyoshige Shigenobu '
        'Yasumasa Tadayoshi Naomasa Naotaka Tadamasa Tadakatsu Takamori Toshimichi Toshizo Isami Shinpachi '
        'Ryoma Shinsaku Kogoro Shintaro',
        '',
        'Matsudaira Honda Sakai Okubo Ishikawa Sakakibara Naito Abe Mizuno Ogasawara Hosokawa Kuroda Asano '
        'Nabeshima Shimazu Mori Yamauchi Todo Hachisuka Uesugi Satake Tsugaru Hotta Inaba Doi Toda Ando Itakura '
        'Okudaira Oishi Saigo Yoshida Katsu Watanabe Ii Date Maeda Ikeda Kato Sakuma Aoyama Nagai Yagyu Toki '
        'Inoue Tsuchiya Kuze Wakizaka Akimoto Makino Nagao Hori Niwa Tsutsui Tanuma Matsumae Nambu Sanada '
        'Mizoguchi Kyogoku Ikoma Hayashi Ota Kondo Hijikata Okita Sakamoto Katsura Takasugi Kido Itagaki Goto '
        'Saito Yamaguchi Suzuki Takahashi Kobayashi Nakamura Yamamoto Ito Shimada Fujita Hirata Sato Murata Ono '
        'Ogyu Arai Nagasawa Matsuura Arima Omura Tachibana Yanagisawa Manabe Torii Honjo Okochi Mogami Hoshina'),
    # source: general knowledge (estimate: yes)
    'farming': group(
        'Ume Take Matsu Tora Kuma Iku Tatsu Sute Natsu Aki Kayo Shina Tome Kame Haru Yae Fuji Nami Sada Toki '
        'Kuni Mitsu Iwa Tsuta Hana Tsuya Miyo Sue Hatsu Kiyo Ine Riku Kiku Tsuru Sen Toku Fuku Kin Gin Sato '
        'Yoshi Tami Ito Masa Tsune Nobu Hisa Shige Fusa Toyo Naka Rin Sayo Chiyo Yasu Mine Kane Tama Taka Teru '
        'Koto Michi Moto Nao Nui Ritsu Suga Sumi Yone Waka Fumi Tetsu Iso Ei Fuyu Fude Hide Ichi Kaku Kana Kiwa '
        'Koma Kura Kume Riyo Sawa Shika Shizu Some Sono Suzu Tae Tane Tomi Tomo Toshi Tsugi Uta Yuki Iyo',
        'Gonbei Sakubei Tasaku Mosuke Yosaku Kyusaku Jinsaku Hachiro Genzo Magoemon Gorobei Matazo Jinzaemon '
        'Kichiji Tomezo Kumazo Torakichi Sankichi Yoshizo Kanzo Heizo Isaku Sakuzo Tokuzo Matsuzo Kamekichi '
        'Ushimatsu Uemon Yazaemon Gonzo Denzo Shichibei Gonsaku Heisaku Kisaku Sosaku Yasaku Rihei Tahei Sahei '
        'Gohei Mohei Ihei Jihei Kihei Sakuemon Magobei Magoshichi Matazaemon Mataemon Jinbei Hachibei Tokubei '
        'Gonroku Gonshichi Kumakichi Kamezo Tokichi Taro Jiro Saburo Shiro Goro Rokuro Shichiro Juro Tarobei '
        'Jirobei Shirobei Rokubei Hanbei Kyuhei Yahei Yasuke Yaichi Kuemon Gosaku Sanzo Rokuzo Ginzo Kinzo '
        'Seizo Tosaku Mosaku Tomekichi Matsukichi Genkichi Kyuzo Chosuke Kisuke Gensuke Mansuke Jusuke Shinsuke '
        'Tasuke Densuke Heikichi Gorosaku Tarosaku',
        '',
        'Kamimura Shimomura Nakamura Kitamura Nishimura Tanaka Yamashita Ishida Hara Ota Ikeda Hayashi '
        'Kawaguchi Hirano Inoue Matsumoto Takeuchi Sakamoto Ogawa Fujita Kawai Ono Uchida Murakami Noguchi '
        'Sugiyama Tsuchiya Yokoyama Okada Iwasaki Suzuki Takahashi Sato Ito Watanabe Kobayashi Kato Yoshida '
        'Yamada Sasaki Yamaguchi Shimizu Yamazaki Ishikawa Saito Maeda Fujii Kondo Endo Aoki Sakai Fukuda Miura '
        'Fujiwara Okamoto Matsuda Nakajima Nakano Harada Tamura Takeda Kaneko Wada Nakayama Ishii Ueda Morita '
        'Shibata Kudo Yokota Miyazaki Miyamoto Takagi Ando Taniguchi Maruyama Imai Takada Fujimoto Ueno '
        'Sugimoto Masuda Hirata Otsuka Chiba Kubo Matsui Iwata Sakurai Kinoshita Matsuo Nomura Kikuchi Sano '
        'Onishi Sugawara Ichikawa Kojima Mizuno Furukawa'),
}

QING_CHINA = {
    # source: general knowledge (estimate: yes)
    'han': group(
        'Guiying Xiulan Yulan Shuzhen Guizhen Yuzhen Xiuzhen Fengying Cuiying Jinlan Yulian Guilan Suzhen '
        'Lanying Qiaoyun Cuilan Aizhen Shuying Huilan Baozhu Jinfeng Caifeng Yufeng Meilan Lianying Xiuying '
        'Hehua Qiuxiang Chunmei Shuyun Jinying Guifang Yinzhu Xiaomei Yuying Fenglan Xiulian Guilian Jinlian '
        'Cuilian Guixiang Suying Yueying Huiying Fengzhen Jinzhen Lizhen Meizhen Guizhi Lanzhi Guihua Juhua '
        'Lanhua Taohua Lihua Xinghua Jinhua Chunhua Qiuhua Cuihua Chunxiang Lanfang Yufang Shufang Cuifang '
        'Xiufang Jinfang Suqin Yuqin Shuqin Guiqin Xiuqin Fengqin Yuyun Cuiyun Xiuyun Caiyun Jinyun Lanzhen '
        'Shufen Guifen Yufen Huifang Shulan Yuhua Huizhen Qiulan Chunlan Guirong Yurong Shurong Xiurong Fengzhi '
        'Yuzhi Xiuzhi Cuizhen Meiying Jinxiu Yuxiu Shuxiu',
        'Dehai Fugui Changgeng Yongfu Shunfa Rongbao Tianci Jinbao Qingyun Dexing Fuquan Yongqing Jinsheng '
        'Baoshan Changshun Laifu Wanfu Shoushan Zhaolin Hongen Tingyu Jishan Mingde Zhenbang Shoulin Guozhen '
        'Hanzhang Liansheng Fuhai Zengxiang Wenbin Guoliang Fuxing Fusheng Fulin Fucheng Fuchang Fushou Changfa '
        'Changfu Changlin Changxing Yongfa Yongsheng Yongchang Yongxiang Dexiang Desheng Decai Deyuan Defu '
        'Deshan Baolin Baoyuan Jinlong Jinyuan Ronghua Rongchang Shunxing Tianxiang Tianfu Wanshan Wanxing '
        'Zhaoxiang Hongzhang Guofan Guoquan Zongtang Zhidong Shikai Bingzhang Yousheng Wenzheng Shichang Mengqi '
        'Zhiyuan Jinrong Guangxu Guanglin Xuehai Wenlong Wenhua Shouqing Shoutian Rongxiang Laishun Laibao '
        'Zhenfa Zhenguo Hanqing Yaoting Zhaoting Shaoting',
        '',
        'Wang Li Zhang Liu Chen Yang Zhao Huang Zhou Wu Xu Sun Hu Zhu Gao Lin He Guo Ma Luo Liang Song Zheng '
        'Xie Han Tang Feng Yu Dong Xiao Cao Cheng Zeng Peng Lu Su Pan Du Ye Wei Jiang Cai Jia Ding Ren Shen Yao '
        'Fu Zhong Yuan Deng Tan Liao Fan Jin Shi Qian Kong Bai Cui Kang Mao Qiu Qin Gu Hou Shao Meng Long Wan '
        'Duan Lei Yin Yi Chang Qiao Lai Gong Wen Pang Yan Hao Niu Tao Xiang Zou Xiong Hong Fang Ji Ou Mo Ling '
        'Rong Kuang Tu Zhuang Shu Bao Le'),
    # source: Wikipedia "Manchu clans", "Viceroy of Zhili", "Viceroy of Liangjiang", "Viceroy of Huguang", "Wenxiu"; feminine list general knowledge (estimate: yes)
    'manchu': group(
        'Shuxian Yurong Wanrong Huifen Shuhua Yuxiu Jingfang Shufang Ruiyun Guixiang Rongfen Defang Jingyi '
        'Yuqing Shulan Rongzhen Yinghua Fengxian Lanxiang Xiuyun Cuifeng Guiqin Shuqin Yuqin Jingzhen Daniu '
        'Erniu Sanniu Siniu Xiaoniu Fuxiang Ruifen Wenxiu Shufen Guifen Yufen Huifang Shuyi Yuhua Jinghua '
        'Ruiqing Rongqing Jingrong Huiqing Shurong Daya Erya Sanya Xiaoya Guiying Yulan Shuzhen Xiuying Yurui '
        'Ruixiu Shuqing Fengying Lanying Cuiying Jinfeng Yuying Huizhen Guizhen Shuying Shuyun Defen',
        'Ronglu Wenxiang Baojun Gangyi Duanfang Ruilin Linggui Chongqi Chonghou Shengyu Yulu Kuijun Jingshan '
        'Yinchang Tieliang Xiliang Lianyuan Chongli Guangshou Yuqian Qishan Ruichang Jinliang Enming Duolonga '
        'Mingliang Shengbao Delenggetai Huaitapu Zhirui Wenqing Mukedengbu Nasutu Omida Mujangga Nergingge '
        'Wenyu Tingyong Natong Maleji Asihi Fulata Shaomubu Gali Heshou Changnai Cabina Qingfu Depei Sazai '
        'Shulin Fusong Changlin Fugang Suringga Funing Tiebao Alinbao Lebao Bailing Ilibu Linqing Bichang '
        'Xianghou Yiliang Kuiyu Ehai Elunte Fumin Maizhu Bandi Arsai Sailenge Xinzhu Yongxing Kaitai Suchang '
        'Aibida Haiming Fulehun Wenshou Sanbao Tuside Shuchang Tecengge Changqing Jingan Quanbao Qingbao Songfu '
        'Taiyong Ruicheng Heshen Agui Fukangan Zhaohui Fuheng Nayancheng Ortai Yinjishan',
        '',
        'Aisin_Gioro Gioro Gualgiya Niohuru Tunggiya Heseri Fuca Yehe_Nara Ula_Nara Hada_Nara Hoifa_Nara Nara '
        'Magiya Irgen_Gioro Sirin_Gioro Donggo Janggiya Uya Sakda Bayara Tatara Socoro Ligiya Hitara Sumuru '
        'Ujala Gorolo Wanggiya Guan Tong Fu Ayan_Gioro Aha_Gioro Susu_Gioro Arute Barin Biru Emoto Gogiya '
        'Sitara Tuseri Weigiya Yanje Erdet Joogiya Wanyan Namdulu Nimaca Yanggiya Lang Jin Zhao Ma Bai Tang Su '
        'Zhang Wang Na Suo Tie Gao Liu Xu Zhou Wu Li Chen'),
    # source: general knowledge (estimate: yes)
    'hakka': group(
        'Xiumei Jiaomei Lanmei Yumei Fengmei Jinmei Chunmei Qiumei Dongmei Guimei Ermei Sanmei Simei Taomei '
        'Lianmei Xuanjiao Lianying Yingniang Jinniang Yuniang Fengniang Xiuniang Lanniang Cuiniang Meiniang '
        'Yuzhen Shuying Jiaoying Guiying Ahfeng Siying Jinhua Ahmei Ahlan Ahjiao Ahying Ahxiu Ahyun Ahzhen '
        'Ahhua Ahgui Ahju Yingmei Hongmei Zhenmei Huamei Xiangmei Yunmei Cuimei Yuanmei Fengjiao Jinjiao '
        'Lanjiao Meijiao Xiujiao Siniang Wuniang Liuniang Qiniang Baniang Erniang Sanniang Yuying Fenglan '
        'Xiulian Guilian Jinlian Cuilian Guixiang Suying Yueying Huiying Fengzhen Jinzhen Lizhen Meizhen Guizhi '
        'Lanzhi Guihua Juhua Lanhua Taohua Lihua Xinghua Chunhua Qiuhua Cuihua Chunxiang Lanfang Yufang Shufang '
        'Cuifang Xiufang Jinfang Suqin Yuqin Shuqin Guiqin Xiuqin Fengqin',
        'Xiuquan Rengan Yunshan Xiuqing Chaogui Dakai Rengda Renfa Fengxiang Jinfa Renlong Tianfu Guangyao '
        'Wenhai Yongfa Zhongliang Dingguo Rongguang Sihai Mingqing Huanzhang Jiaxiang Fuchang Delin Shaoxiang '
        'Zhaohe Ahfu Agui Ashun Asheng Along Ahai Changhui Xiucheng Yucheng Wenguang Fangbo Bishi Yalai Zunxian '
        'Richang Fengjia Yongfu Ahfa Ahcai Ahxing Ahde Ahlin Ahquan Ahwang Ahsan Ahsi Ahyou Ahlong Ahtian '
        'Jinlong Fuxing Fusheng Fulin Changfa Yongsheng Yongchang Dexiang Desheng Decai Defu Rongchang '
        'Tianxiang Wanshan Zhaoxiang Guofu Guangxiang Renhe Renshou Wenfa Wenxing Jiaxing Shoushan Xingfa '
        'Shunfa Rongbao Jinsheng Baoshan Changshun Laifu Wanfu Mingde Fuquan Yongqing Dexing Qingyun Tianci '
        'Jinbao',
        '',
        'Chen Li Huang Zhang Liu Lin Zeng Wu Luo Xie Ye Zhong Peng Qiu Liao Yang He Xu Jiang Lai Fan Hong Wen '
        'Tang Gu Wei Hou Yu Zhuo Tu Feng Deng Su Zhuang Xiao Cai Guo Zhou Ma Gao Fu Ou Fang Cheng Pan Kang Yan '
        'Hu Shi Zou Mo Ling Rong Yi Kuang Pang Gong Zhao Sun Zhu Song Lu Dong Yuan Cao Wang Rao Gan Ke Lan Ning '
        'Zhan Yin Kong Mai Lei Jian Tian Ren Shen Zheng Jin Mei Wan Xiong Yao Leng Ding Mao'),
}

OTTOMAN = {
    # source: general knowledge (estimate: yes)
    'turkish': group(
        'Ayse Fatma Emine Hatice Zeynep Hafize Saliha Nefise Rukiye Hayriye Nazife Sadiye Saide Hamide Habibe '
        'Esma Sakine Meryem Zehra Naile Halime Fitnat Gulsum Nazli Mihri Pakize Nadide Cemile Feride Behiye '
        'Refika Atiye Safiye Huriye Adile Aliye Asiye Azize Bedriye Belkis Dilber Durdane Emetullah Fahriye '
        'Fehime Gulizar Gulnihal Gulfem Gulbahar Hacer Halide Hanife Hasibe Hurrem Ikbal Kerime Latife Leman '
        'Leyla Makbule Mahmure Melek Melike Mevhibe Munire Muzeyyen Nakiye Nebahat Necmiye Nesibe Nezihe Nigar '
        'Nimet Rabia Rahime Rasime Remziye Saadet Sabiha Samiye Selma Semiha Sukriye Sureyya Tevhide Ulviye '
        'Vasfiye Vecihe Zekiye Zubeyde Zuleyha Fikriye Lutfiye Mihrimah Kamile Nuriye Hamdiye Muazzez Saniye '
        'Seniha',
        'Mehmed Ahmed Ali Mustafa Hasan Huseyin Ibrahim Ismail Osman Suleyman Halil Yusuf Abdullah Hakki Hilmi '
        'Rifat Sadik Tevfik Kamil Emin Salih Riza Nuri Halim Fehmi Edhem Ragip Necib Sevket Fuad Zeki Arif Omer '
        'Bekir Abdurrahman Adil Akif Asim Aziz Bahri Bedri Cemal Cevdet Celal Cafer Davud Enver Fahri Faik '
        'Fazil Ferid Fikri Galib Hafiz Hamdi Hamid Hayri Hikmet Hulusi Husnu Ihsan Ilyas Izzet Kadir Kazim '
        'Kemal Lutfi Mahmud Mahir Mazhar Murad Musa Muhiddin Nazim Nazif Necati Nusret Rauf Recep Resid Rustem '
        'Sabri Said Selim Sami Seyfi Sukru Talat Tahir Yakub Yahya Yunus Zekeriya Ziya Ramazan Hamza Haydar '
        'Idris Ismet Nafiz',
        '',
        'Ahmedoglu Kasapzade Hoca Hacioglu Mehmedoglu Hasanoglu Osmanoglu Alioglu Mustafaoglu Ibrahimoglu '
        'Kalaycioglu Demircioglu Karaosmanoglu Cerrahzade Imamzade Hafizzade Kadizade Mollazade Bakkal Berber '
        'Terzi Kunduraci Haci Arnavut Topal Deli Kara Uzun Sarioglu Bostanci Hamal Kaptan Abdullahoglu '
        'Yusufoglu Ismailoglu Suleymanoglu Haliloglu Huseyinoglu Omeroglu Bekiroglu Mahmudoglu Velioglu '
        'Kocaoglu Karaoglu Bayraktar Kasap Kalayci Demirci Attar Sarraf Kuyumcu Aktar Debbag Sarac Nalbant '
        'Semerci Ekmekci Kahveci Helvaci Sekerci Tutuncu Bicakci Kazanci Boyaci Hallac Mumcu Sabuncu Kantarci '
        'Camci Ciftci Coban Gemici Hamamci Simitci Bosnali Laz Cerkez Tatar Halepli Selanikli Konyali Kayserili '
        'Trabzonlu Erzurumlu Sivasli Bursali Edirneli Izmirli Bagdatli Kirimli Misirli Kel Sari Kizil Kucuk '
        'Koca Hafiz Molla Seyyid Dervis'),
    # source: general knowledge (estimate: yes)
    'greek': group(
        'Maria Eleni Aikaterini Sofia Anna Despina Kalliopi Evanthia Theodora Vasiliki Eirini Zoe Chrysoula '
        'Angeliki Alexandra Smaragda Efrosyni Paraskevi Kyriaki Marigo Evdokia Anastasia Ioanna Georgia '
        'Polyxeni Fotini Stamatia Argyro Penelope Euterpe Chrysanthi Evangelia Eleftheria Panagiota Dimitra '
        'Konstantina Stavroula Chrysi Asimina Athina Eftychia Sotiria Triantafyllia Marina Pelagia Christina '
        'Antonia Varvara Evgenia Kassiani Glykeria Magdalini Areti Thekla Ourania Kalliroi Afroditi Domna '
        'Theofano Efthymia Melpomeni Lambrini Archontoula Loukia Kleopatra Olga Aspasia Kalypso Myrsini '
        'Charikleia Andromachi Antigoni Ifigeneia Theoni Agathi Evdoxia Rodanthi Anthi Smaro Katina Frosso '
        'Stamatoula Kalomoira Marigoula Sevasti Olympia Afentoula Paschalina Garyfallia Krystallo Zafeira Dafni '
        'Anneta Fani Erasmia Eugenia Ermioni',
        'Georgios Ioannis Konstantinos Dimitrios Nikolaos Vasileios Panagiotis Christos Athanasios Antonios '
        'Stylianos Michail Alexandros Emmanouil Theodoros Stavros Pavlos Petros Spyridon Evangelos Charalambos '
        'Apostolos Leonidas Grigorios Andreas Stefanos Kyriakos Anastasios Prodromos Ilias Aristeidis Zacharias '
        'Sotirios Lambros Fotios Eleftherios Thrasyvoulos Miltiadis Themistoklis Periklis Sokratis Xenofon '
        'Epameinondas Achilleas Odysseas Kosmas Damianos Lazaros Matthaios Markos Loukas Filippos Thomas '
        'Iakovos Gerasimos Dionysios Anagnostis Stamatios Efstathios Efstratios Ignatios Kyrillos Polychronis '
        'Chrysostomos Neofytos Sofoklis Diamantis Christoforos Savvas Panteleimon Timotheos Iraklis Nikitas '
        'Argyris Zisis Sarantis Triantafyllos Vlasios Anestis Ioakeim Kallinikos Manolis Pantelis Konstantis '
        'Yannis Christodoulos Theofilos Paraskevas Tryfon Rigas Kanellos Mavroudis Kleanthis Stergios '
        'Agathangelos Evangelinos Germanos Meletios Anthimos Dorotheos',
        '',
        'Papadopoulos Karatzas Mavrokordatos Zografos Vlastos Zarifis Georgiadis Ioannidis Konstantinidis '
        'Nikolaidis Dimitriadis Hatziioannou Oikonomou Theodoridis Christodoulou Sideridis Pappas Vafiadis '
        'Eugenidis Stavridis Kalfas Antoniadis Pavlidis Michailidis Hatzopoulos Vasileiou Raftopoulos Mavros '
        'Siniossoglou Baltazzi Skouloudis Ypsilantis Mavrogenis Soutsos Karatheodori Mourouzis Kallimachis '
        'Rallis Negrepontis Zervos Argyropoulos Mavromichalis Kolokotronis Botsaris Kanaris Miaoulis '
        'Koundouriotis Tombazis Zaimis Deligiannis Syngros Rodokanakis Agelastos Papadakis Papageorgiou '
        'Papanikolaou Papadimitriou Georgiou Nikolaou Dimitriou Konstantinou Ioannou Athanasiou Antoniou Petrou '
        'Panagiotou Alexiou Kyriakidis Kalogeropoulos Lambrou Makris Kontos Karagiannis Karamanlis Hatzidakis '
        'Hatzigeorgiou Hatzichristou Theodorou Stamatiou Vlachos Andreadis Anagnostou Mavrommatis Kostopoulos '
        'Sarantidis Prodromou Spanos Galanis Lekkas Kalogeras Papazoglou Tsakiroglou Kehagioglou Kazazoglou '
        'Hatziantoniou Paspatis Psychas Skaramangas Christakis Manolakis'),
    # source: Houshamadyan, "The Armenians of Hazari" genealogy; rest general knowledge (estimate: yes)
    'armenian': group(
        'Mariam Anna Takuhi Zabel Srpuhi Hripsime Arshaluys Nvart Siranush Haiganush Satenik Lusin Gayane '
        'Anahid Hermine Elmas Mari Aznive Vartanush Shushan Zaruhi Araksi Hranush Nazeli Makruhi Yeranuhi '
        'Varsenik Ovsanna Sirarpi Agavni Diruhi Marta Akabi Arpenig Lousia Nartouhi Nazlou Yeghsa Vergin '
        'Santoukht Shoghagat Satenig Anoush Astghik Azadouhi Berjouhi Eghisapet Iskouhi Kohar Noyemi Parantsem '
        'Seta Sona Zepure Zvart Arousyak Hasmik Sirvart Vartuhi Armenouhi Yepraksi Mayranush Almast Altun '
        'Gulizar Khatun Shamiram Nunufar Arpine Hripsik Lusaber Margarit Nazik Perouz Rebeka Takouhi Yeghisabet '
        'Zarouhi Heghine Knar Ashkhen',
        'Hagop Garabed Krikor Boghos Bedros Hovhannes Mardiros Ohannes Sarkis Kevork Haroutioun Mihran Nishan '
        'Avedis Arshag Dikran Vahan Levon Aram Nerses Mesrob Zareh Setrak Simon Kaloust Vartan Khachadur Diran '
        'Hrant Onnik Minas Hovsep Aghajan Aleksan Beglar Ghougas Giragos Karekin Khosrov Moushegh Nigoghos '
        'Pilibos Shmavon Soghomon Antranig Haigaz Herant Mateos Setrag Yessai Vram Apkar Arakel Artin Ashod '
        'Avak Baghdasar Barkev Garbis Gaspar Ghazar Hampartsoum Haig Hamazasp Hovnan Kerop Khoren Manoog Markar '
        'Megerditch Melkon Movses Nazaret Nubar Parsegh Rupen Sahag Sempad Serop Stepan Tavit Toros Vahram '
        'Varoujan Vartkes Yervant Yeghia Zaven Zohrab Arpiar Torkom Asadour Antranik Ardashes Tateos Murad '
        'Mardig Hovakim Mikayel Abraham',
        '',
        'Gulbenkian Dadian Balyan Duzian Bezjian Kazazian Hagopian Garabedian Krikorian Boghosian Bedrosian '
        'Ohanian Sarkisian Kevorkian Haroutiounian Mardirosian Nishanian Avedisian Tashjian Kouyoumjian '
        'Demirjian Yazejian Terzian Bakalian Kalfayan Papazian Topalian Hovsepian Abajian Simonian Odian '
        'Kalebjian Ajemian Amirkhanian Bekerian Gosdanian Hovnanian Marashlian Nersesian Depoian Altiparmakian '
        'Der_Mateosian Der_Pilibosian Soghigian Yarumian Kalousdian Parounagian Abrahamian Arakelian Artinian '
        'Avakian Baghdasarian Berberian Chakmakjian Esayan Gasparian Ghazarian Hampartsoumian Kalustian '
        'Kassabian Kazanjian Khachadourian Manoogian Markarian Megerdichian Melkonian Minassian Movsesian '
        'Nazarian Nubarian Panossian Parsekian Sahagian Sarafian Semerjian Shahinian Stepanian Tavitian '
        'Torosian Vahramian Vartanian Yeghiayan Zakarian Zohrabian Chilingirian Ekmekjian Missakian Pashayan '
        'Tokatlian Utujian Hekimian Boyajian Kurkjian Tutunjian Mouradian Mekhitarian Antreassian Aslanian '
        'Dadrian Noradounghian'),
    # source: issendai.com "Jewish Women's Names in 16th-/17th-Century Istanbul" (Haskoy gravestones); RFP Europe "Sephardic Onomastics"; rest general knowledge (estimate: yes)
    'sephardic': group(
        'Rahel Reina Sol Luna Estrea Bulisa Djoya Vida Allegra Sara Ester Rivka Lea Miryam Klara Rosa Buena '
        'Fortuna Oro Perla Sultana Benvenida Gracia Mazal Palomba Rebeka Djamila Flor Signora Merkada Simha '
        'Dudu Malka Nehama Esperansa Kadun Margalit Kalo Reni Bohora Yilda Elmas Fidan Simi Hanna Bella Blanka '
        'Dona Zimbul Zafira Tamar Yohevet Dvora Sarina Behora Djentil Preciada Kamila Mazaltov Bienvenida Rena '
        'Ana Viktoria Esterina Rahelika Grasia',
        'Avram Isak Yakov Moshe Yosef Shemuel Shabetay Haim Bohor Nissim Eliau Yehuda Menahem Salomon Mordehai '
        'Rafael Daniel Aron David Bension Mair Yom_Tov Zaharia Jako Leon Vitali Gavriel Pinhas Hezkia Albert '
        'Ezra Marko Meshullam Beto Buko Eliezer Mercado Nahum Ovadia Shaul Shimon Shalom Sadik Binyamin Hananel '
        'Matatia Menashe Asher Efraim Yisrael Natan Rahamim Senior Tuvia Yehezkel Elisha Yona Elazar Nehemia '
        'Vidal Avner Hayim Bensiyon Yeshaya Gedalia Sabetay Yitzhak Abraham Mose Isaac Salamon Haskel Behor '
        'Yuda',
        '',
        'Behar Levi Kohen Alhadeff Abravanel Benveniste Camondo Carasso Franco Gabay Hasson Halfon Eskenazi '
        'Farhi Mizrahi Navarro Toledano Saporta Amado Algranti Baruh Bensussan Kamhi Pardo Policar Russo '
        'Taragan Uziel Varon Danon Ventura Arditi Mitrani Mallah Zakuto Bessudo Taranto Faraggi Maestro Atias '
        'Prezenti Alegri Stroumtsa Bichacho Aguadish Melamed Mevorakh Abulafia Adato Albukrek Algazi Almosnino '
        'Amar Angel Arie Benardete Benbassat Benezra Benmayor Benrubi Benusiglio Bourla Calderon Capon Covo '
        'Crispin Elnecave Errera Esformes Florentin Gattegno Hananel Hazan Israel Karmona Kastoryano Matalon '
        'Menashe Molho Nahmias Nahum Pinto Perahia Recanati Romano Salem Saltiel Sasson Sciaky Semo Sidi '
        'Soriano Strumza Tiano Yacoel Abastado Amiel Cuenca Galante Habib'),
}

ANCIENT_ROME = {
    # source: general knowledge (estimate: yes)
    'roman': group(
        'Julia Cornelia Claudia Antonia Valeria Caecilia Flavia Domitia Sulpicia Pompeia Fabia Aemilia Junia '
        'Livia Octavia Calpurnia Licinia Plotina Annia Vibia Statilia Servilia Marcia Tullia Porcia Agrippina '
        'Faustina Sabina Plautia Ulpia Paulina Pomponia Sempronia Terentia Lucilla Aelia Antistia Atilia '
        'Caesonia Cassia Clodia Cominia Didia Fulvia Furia Gellia Helvia Herennia Hortensia Laelia Lollia '
        'Lucretia Manlia Minicia Mucia Munatia Naevia Nonia Oppia Papiria Petronia Pinaria Plancia Popillia '
        'Postumia Quinctia Rubellia Rutilia Salvia Scribonia Seia Sentia Sergia Sextia Silia Sosia Titia '
        'Trebonia Vipsania Vettia Vitellia Volumnia Atia Arria Aquilia Curtia Egnatia Fadia Gavia Hostilia '
        'Mamilia Mummia Ummidia Veturia Volusia Matidia Drusilla Priscilla Marcella Prisca',
        'Gaius Lucius Marcus Publius Quintus Titus Tiberius Gnaeus Aulus Sextus Decimus Servius Spurius Manius '
        'Appius Numerius Mamercus Vibius Rufus Secundus Maximus Severus Priscus Gallus Celer Crispus Sabinus '
        'Fuscus Paullus Proculus Clemens Firmus Albinus Balbus Bassus Blaesus Brutus Calvus Capito Catulus '
        'Celsus Cotta Crassus Drusus Flaccus Florus Fronto Geminus Glabrio Justus Lentulus Lepidus Longinus '
        'Longus Lupus Macer Marcellus Metellus Naso Nepos Niger Paetus Pius Pollio Pulcher Regulus Rufinus '
        'Rusticus Saturninus Scaevola Scaurus Seneca Silanus Silvanus Strabo Taurus Torquatus Varro Varus Verus '
        'Agricola Aquila Atticus Avitus Bibulus Caepio Camillus Cicero Cinna Cato Scipio Dolabella Labeo '
        'Lucullus Messala Nerva Piso Plancus Tubero Vindex',
        '',
        'Julius Cornelius Claudius Valerius Caecilius Flavius Domitius Sulpicius Pompeius Fabius Aemilius '
        'Junius Livius Octavius Calpurnius Licinius Annius Vibius Statilius Servilius Marcius Tullius Porcius '
        'Plautius Ulpius Antonius Sempronius Cassius Fulvius Terentius Petronius Pomponius Acilius Aelius '
        'Atilius Antistius Arrius Caesius Calidius Caninius Clodius Coelius Cominius Curtius Didius Egnatius '
        'Fannius Furius Gabinius Gavius Gellius Helvius Herennius Hirtius Hortensius Hostilius Laelius Lollius '
        'Lucretius Manlius Memmius Minucius Mucius Munatius Naevius Nonius Numisius Oppius Papirius Pedanius '
        'Pinarius Plancius Plotius Popillius Postumius Quinctilius Quinctius Rabirius Rubellius Rutilius '
        'Salvius Scribonius Seius Sentius Sergius Sextius Silius Sosius Titius Trebonius Varius Vergilius '
        'Verginius Vettius Vipsanius Vitellius Volumnius Vinicius Atius Aquilius'),
    # source: Arctos (journal.fi) study of female tria nomina; rest general knowledge (estimate: yes)
    'greek': group(
        'Chloe Tyche Helpis Phoebe Daphne Irene Eutychia Agathe Chrysis Eutyche Nymphe Syntyche Tryphaena '
        'Tryphosa Euhodia Lydia Persis Doris Zosime Callityche Erotis Thais Philumena Glycera Nice Moschis '
        'Charis Hermione Antiochis Stephanis Euphrosyne Hedone Nicephoris Glycenna Acte Apphia Aphrodisia '
        'Artemisia Athenais Berenice Callisto Chreste Dorcas Eunice Euphemia Galene Iris Isias Lais Melissa '
        'Myrtale Nais Olympias Pamphila Phila Philematium Phyllis Psyche Sophia Stratonice Syra Thalia Theodote '
        'Thallusa Zoe Eutychis Philete Glyce Selene Ammia Arescusa Euplia Stephane Rhodine Charite Chrysogone '
        'Epigone Pieris Calliope Musa Chloris Daphnis Cytheris Thymele Eucharis Prote Elpis Heuresis Nike '
        'Hilaritas',
        'Hermes Eros Philemon Onesimus Epaphroditus Narcissus Pallas Diogenes Eutychus Trophimus Hermas '
        'Philetus Alexander Dionysius Apollonius Zosimus Antiochus Heraclides Aristobulus Chrysippus Callistus '
        'Epictetus Philologus Isidorus Sosthenes Stephanus Theophilus Tychicus Agathocles Demetrius Menander '
        'Herodion Asclepiades Anicetus Antigonus Apollodorus Ariston Artemidorus Athenodorus Attalus '
        'Callimachus Chrysogonus Diodorus Diophantus Dorotheus Epagathus Epaphras Eumenes Euodus Euphrates '
        'Eutyches Glaucus Hermogenes Hilarus Iason Menophilus Myron Nicanor Nicephorus Nicias Nicomedes Olympus '
        'Onesiphorus Pamphilus Parthenius Phileros Philippus Philocalus Phoebus Symphorus Syntrophus Thallus '
        'Theodorus Thrasyllus Timotheus Tryphon Zethus Zoilus Euphemus Hyacinthus Lysimachus Agathopus '
        'Antipater Aristides Callinicus Diadumenus Eutactus Helius Hesychus Lycus Nereus Nicostratus '
        'Philargyrus Philocrates Pothinus Sosibius Telesphorus Zenon Zoticus Abascantus',
        '',
        'Julius Claudius Flavius Ulpius Cocceius Domitius Antonius Valerius Cornelius Aemilius Caecilius '
        'Licinius Pompeius Sempronius Terentius Statilius Vettius Lollius Mussius Naevius Publicius Sallustius '
        'Marcius Annaeus Seius Herennius Plotius Tullius Volusius Calpurnius Acilius Aelius Atilius Antistius '
        'Arrius Caesius Calidius Caninius Clodius Coelius Cominius Curtius Didius Egnatius Fannius Furius '
        'Gabinius Gavius Gellius Helvius Hirtius Hortensius Hostilius Laelius Lucretius Manlius Memmius '
        'Minucius Mucius Munatius Nonius Numisius Oppius Papirius Pedanius Pinarius Plancius Popillius '
        'Postumius Quinctilius Quinctius Rabirius Rubellius Rutilius Salvius Scribonius Sentius Sergius Sextius '
        'Silius Sosius Titius Trebonius Varius Vergilius Verginius Vipsanius Vitellius Volumnius Vinicius Atius '
        'Aquilius Considius Mummius Ovidius Ummidius Veturius Caesonius Fadius Asinius'),
    # source: general knowledge (estimate: yes)
    'provincial': group(
        'Prima Secunda Tertia Quarta Maxima Severa Saturnina Januaria Fortunata Victorina Honorata Donata '
        'Felicula Rogata Urbica Verecunda Regina Namgedde Successa Ingenua Materna Candida Optata Quieta '
        'Restituta Crescentia Rustica Lepidina Victoria Primitiva Felicitas Perpetua Concessa Donatilla Emerita '
        'Fausta Feliciana Felicissima Gaudiosa Hilaria Justina Primula Procula Quintina Romana Rufina Rogatiana '
        'Sabina Secundina Silvana Tertulla Urbana Valentina Dativa Pia Bona Sperata Marcia Julia Aemilia '
        'Claudia Flavia Valeria Cornelia Caecilia Antonia Sulpicia Paulina Maximilla Vitalis Benenata Exorata '
        'Fidelis Placida Quintilla Saturnilla Victorica Crescentilla Vibia Sophonisba',
        'Saturninus Rogatus Donatus Fortunatus Felix Victor Januarius Honoratus Vitalis Secundus Tertius Primus '
        'Crescens Faustus Ingenuus Datus Optatus Successus Verecundus Senecio Cintusmus Bellicus Catavignus '
        'Vepogenus Brigomaglos Tasciovanus Hanno Himilco Mago Namphamo Restitutus Rusticus Bassus Candidus '
        'Celer Clemens Concessus Crescentianus Datianus Emeritus Exuperatus Faustinus Felicianus Festus '
        'Florentius Fronto Gaudentius Hilarus Justus Liberalis Lucianus Marcellinus Martialis Maternus '
        'Maximianus Modestus Paternus Peregrinus Pudens Quietus Quintianus Romanus Rufinus Sabinus Saturus '
        'Secundinus Servandus Severianus Silvanus Speratus Tertullus Urbanus Ursus Valens Verus Victorinus '
        'Dannicus Sita Veldedeius Litugenus Tancinus Viducus Cintugnatus Atrectus Bostar Gisco Adherbal '
        'Bomilcar Hasdrubal Hamilcar Iddibal Rufus Severus Maximus Priscus Gallus Marcus Gaius Lucius Titus',
        '',
        'Julius Claudius Flavius Ulpius Cocceius Pompeius Valerius Antonius Cornelius Caecilius Fabius Junius '
        'Licinius Aemilius Sempronius Maternius Secundinius Victorius Primius Justinius Sentius Sulpicius '
        'Marius Vibius Gargilius Sittius Egnatius Helvius Atilius Arruntius Aelius Septimius Caelius Cassius '
        'Domitius Gavius Marcius Memmius Minucius Octavius Petronius Pomponius Postumius Sallustius Seius '
        'Sergius Servilius Sextius Terentius Titius Vettius Volusius Calpurnius Mustius Nonius Plautius '
        'Aufidius Avidius Aquilius Fadius Granius Hortensius Lollius Manilius Novius Numisius Papirius Satrius '
        'Statilius Tullius Varius Cosinius Lucretius Furius Herennius Livius Fulvius Annius Arrius Caesius '
        'Fabricius Gellius Iulius Naevius Oppius Quintius Rutilius Silius Vitellius Volumnius Cominius Curtius '
        'Didius Manlius Pinarius Popillius Sosius'),
}

MUGHAL_INDIA = {
    # source: general knowledge (estimate: yes)
    'muslim': group(
        'Fatima Zainab Ayesha Khadija Maryam Amina Halima Sakina Rabia Zubaida Hamida Salima Rahima Karima '
        'Jamila Hasina Gulnar Shirin Zahra Habiba Latifa Najma Sultana Bilqis Ruqaiya Mahbuba Asma Saliha '
        'Dilaram Mehrunnisa Gulbadan Sharifa Gulrukh Jahanara Roshanara Zebunnisa Arjumand Aliya Anjuman Azra '
        'Bano Dilshad Farhat Farzana Firdaus Gulshan Gulzar Hafiza Husna Iffat Ishrat Kaniz Khurshid Kulsum '
        'Laila Mahmuda Mahjabin Mehr Mumtaz Munira Nargis Nasreen Naseem Nigar Noor Parveen Qamar Rahila Raziya '
        'Rehana Roshan Safiya Saira Sajida Salma Shahida Shamsa Sughra Tahira Taj Wahida Yasmin Zeenat Zuleikha '
        'Badrunnisa Gauhar Ladli Maham Gulchehra Dildar Khanzada Bakhtunnisa Qudsia Atiya Aqiqa Bibi Hajra Hura '
        'Jannat Khatun',
        'Muhammad Ahmad Ali Hasan Husain Abdullah Abdul_Karim Abdul_Rahim Ismail Ibrahim Yusuf Daud Sulaiman '
        'Qasim Jafar Mahmud Farid Nur_Muhammad Sher Khizr Mansur Rahmat Hafiz Karim Latif Salim Murad Bahadur '
        'Fazl Inayat Rustam Hamid Nasir Abdul_Qadir Abdul_Aziz Abdul_Hamid Abdul_Latif Abdul_Majid Abdul_Wahid '
        'Abul_Fazl Abul_Hasan Alam Amir Anwar Asad Ashraf Aslam Azam Aziz Baqir Burhan Dilawar Faiz Fateh '
        'Ghulam Ghulam_Muhammad Habib Haidar Hakim Hamza Hashim Iftikhar Ikram Iqbal Jalal Jamal Jamil Kamal '
        'Kamran Khalil Mahdi Masud Mubarak Muhsin Munawwar Murtaza Mustafa Muzaffar Nadir Najib Nasrullah Nizam '
        'Qadir Qutb Rafi Rashid Raza Sadiq Saif Sadullah Shafi Shahbaz Shams Shuja Sikandar Tahir Umar Usman '
        'Wali Yaqub',
        '',
        'Khan Shaikh Sayyid Mirza Beg Ansari Siddiqui Qureshi Lodi Barlas Chughtai Bukhari Naqvi Rizvi Hashmi '
        'Farooqi Usmani Gilani Qadiri Chishti Badakhshi Husaini Bilgrami Tirmizi Kirmani Shirazi Isfahani '
        'Mashhadi Kashmiri Abbasi Yusufzai Kazmi Jafri Zaidi Abidi Niazi Afridi Durrani Bangash Kakar Tareen '
        'Ghori Suri Sherwani Lohani Khattak Qidwai Hamadani Samarqandi Tabrizi Khurasani Herati Kabuli Lahori '
        'Dehlavi Badauni Sarhindi Jaunpuri Multani Sindhi Qazi Mufti Munshi Sabri Nizami Suhrawardi Naqshbandi '
        'Taqvi Baloch Uzbek Turkman Arghun Tarkhan Kokaltash Mewati Rohilla Jalali Haqqani Firdausi Hakim '
        'Kamboh Rangrez Mughal Pathan Afghan Shah Habshi Barha'),
    # source: general knowledge (estimate: yes)
    'hindu': group(
        'Sita Radha Lakshmi Parvati Ganga Yamuna Kamala Savitri Durga Gauri Saraswati Tulsi Rukmini Champa '
        'Chameli Malati Kausalya Anandi Bhagwati Devaki Godavari Janki Kesar Kunti Padma Sundari Uma Lilavati '
        'Mohini Hira Phulmati Annapurna Ahalya Amba Ambika Anasuya Bhagirathi Chandra Chandravati Damayanti '
        'Gita Gomti Indu Jaya Kalyani Kanta Kasturi Kaveri Kishori Kumudini Lalita Madhavi Mainavati Manorama '
        'Mira Mukta Nandini Narmada Nirmala Pushpa Rajeshwari Rama Rambha Rani Rupmati Sarala Shanta Sharda '
        'Shobha Subhadra Sujata Sulochana Sumitra Sushila Tara Triveni Vimala Vrinda Yashoda Kalawati Bhanumati '
        'Sumati Shakuntala Chandrakala Rajmati Anjana Ratna Basanti Bela Jamuna Mangala Moti Panna Prabha Rupa '
        'Sona Gangabai Dhanvanti Hemlata',
        'Ram Krishna Gopal Govind Hari Mohan Shyam Balram Kishan Narayan Raghunath Tukaram Keshav Madhav '
        'Ram_Das Mathura_Das Jagannath Gangadhar Damodar Shankar Mahadev Ganesh Lalchand Sundar Dayaram Gokul '
        'Banarasi Bhagwan_Das Hiranand Sitaram Virji Shantidas Anand Balkrishna Banwari Bihari Brij Dinanath '
        'Dwarka_Das Ganga_Ram Ganpat Ghanshyam Girdhar Gopinath Gulab Hira_Lal Ishwar Jagdish Jairam Kalyan '
        'Kanhaiya Kashinath Lakshman Madan Mahesh Manohar Mukund Nandlal Narsingh Parmanand Prabhu Purushottam '
        'Radhakrishna Raghav Ramchandra Ram_Prasad Ramnath Ratan Raghubir Shiv Shivram Shridhar Sukhdev '
        'Tara_Chand Tulsidas Vishnu Vishwanath Vithal Yashwant Chaturbhuj Daulat_Ram Devidas Jivan Kalicharan '
        'Kishore Lakshmidas Madho Mangal Motilal Narottam Premchand Tikaram Todar Bhimji Devji Lalji Premji '
        'Ramji Harkishan Birbal',
        '',
        'Mishra Tiwari Pandey Dubey Shukla Chaturvedi Trivedi Joshi Bhatt Dikshit Upadhyay Agarwal Khatri Mehta '
        'Shah Seth Verma Saxena Mathur Srivastava Nagar Desai Patil Deshmukh Kulkarni Pandit Chaudhuri Mazumdar '
        'Basu Ghosh Mitra Datta Sen Vora Jhaveri Sharma Dwivedi Vajpeyi Awasthi Agnihotri Tripathi Pathak '
        'Shastri Sinha Kapoor Malhotra Nigam Bhatnagar Kulshreshtha Gupta Goel Garg Mittal Bansal Maheshwari '
        'Chatterjee Banerjee Mukherjee Bhattacharya Chakraborty Ganguly Das Roy Guha Sarkar Bhonsle Jadhav '
        'Pawar Shinde Gaikwad Holkar Gokhale Apte Bhide Phadke Ranade Deshpande Parikh Modi Gandhi Dave Vyas '
        'Pandya Raval Thakkar Patel Iyer Iyengar Rao Reddy Naidu Pillai Nair Menon Chettiar Mudaliar Kaul Raina '
        'Dhar Zutshi'),
    # source: Wikipedia "Rathore dynasty" (branches, rulers), "List of Rajput clans"; rest general knowledge (estimate: yes)
    'rajput': group(
        'Padmavati Karnavati Jaivanta Mira Hansa Tara Sajjan_Kanwar Chand_Kanwar Ratan_Kanwar Gulab_Kanwar '
        'Sugan_Kanwar Kishan_Kanwar Indra_Kanwar Roop_Kanwar Anand_Kanwar Bhanwar_Kanwar Champa_Kanwar '
        'Phool_Kanwar Kesar_Kanwar Suraj_Kanwar Dhan_Kanwar Man_Bai Hira_Bai Lakshmi_Bai Rupa_Bai Sona_Bai '
        'Ajab_Kanwar Jas_Kanwar Ganga_Bai Padma_Kanwar Shyam_Kanwar Umade Gyan_Kanwar Prem_Kanwar Sukh_Kanwar '
        'Mohan_Kanwar Jatan_Kanwar Sardar_Kanwar Raj_Kanwar Moti_Kanwar Sohan_Kanwar Lal_Kanwar Chandra_Kanwar '
        'Mehtab_Kanwar Badan_Kanwar Tej_Kanwar Sundar_Kanwar Amar_Kanwar Tara_Bai Rama_Bai Gauri_Bai Kamla_Bai '
        'Champa_Bai Ratan_Bai Jamna_Bai Kesar_Bai Gulab_Bai Mohan_Bai Sundar_Bai Radha_Bai Sita_Bai Kishori_Bai '
        'Phool_Bai Dhan_Bai Chand_Bai Durgavati Panna Krishna_Kumari Karmavati Rupmati Jaswant_Kanwar '
        'Gordhan_Kanwar Vijay_Kanwar Saubhagya_Kanwar Nathi_Bai Dhapu_Bai Jaswant_Bai Kanku_Bai Mehtab_Bai '
        'Pan_Kanwar Achal_Kanwar Jawahar_Kanwar Bhoor_Kanwar Rajkumari Ajab_De Laxmi_Kanwar Shiv_Kanwar '
        'Indu_Kanwar Lalita_Kanwar Kishori_Kanwar Dal_Kanwar Abhay_Kanwar',
        'Pratap Amar Karan Jagat Man Jaswant Gaj Ajit Bhim Ratan Sur Jai Bishan Chandrasen Maldeo Jaimal Patta '
        'Raghunath Kesri Hammir Anand Prithviraj Kalyan Kumbha Sangram Sujan Indra Bhupat Udai Mukund Durgadas '
        'Bhagwant Satal Biram Ganga Chunda Ranmal Suja Raipal Salkha Kanhadev Bakht Umaid Hanwant Abhay '
        'Bakhtawar Bharmal Bhoj Dalpat Daulat Dungar Fateh Gopal Jagmal Jodha Jujhar Kanha Kishor Lunkaran '
        'Madho Mokal Raimal Shakti Surajmal Takhat Tej Vijay Zorawar Ummed Bakhat Ram Kirat Bika Jaitsi Rai '
        'Anup Padam Surat Sawant Sabal Zalim Hari Ishwari Bhawani Bijay Chandrabhan Dhiraj Govardhan Hamir_Dev '
        'Jagannath Jawahar Kalyanmal Kishan Lakshman Mahendra Nahar Narpat Pratap_Mal Rupsi Sardul',
        '',
        'Singh Rathore Sisodia Kachhwaha Chauhan Hada Bhati Parmar Solanki Tomar Jhala Gaur Chandel Bundela '
        'Baghela Guhilot Shekhawat Champawat Jadeja Deora Sengar Bais Raghuvanshi Bhadoria Gaharwar Katoch '
        'Pundir Bargujar Khichi Songara Kumpawat Jodha Jaitmalot Kandhalot Karamsot Mahecha Rupawat Barsinghot '
        'Raikwar Jaitawat Bika Chudawat Ranawat Shaktawat Mertiya Karnot Bidawat Udawat Dahiya Parihar '
        'Chandrawat Naruka Rajawat Nathawat Bikawat Sodha Gohil Chudasama Jadon Dikshit Gautam Kaushik Bisen '
        'Sombanshi Suryavanshi Jamwal Pathania Jaswal Guleria Chib Rana Thakur Banaphar Kalhans Nikumbh '
        'Sikarwar Dhandhal Kachhawa Bhatti Panwar Pratihar Rathod Sisodiya Chandela Tanwar Yaduvanshi Kalyanot '
        'Kotwal Mandawat Akhawat Shivrajot'),
}

STORYBOOK = {
    'plain': group(
        'Hester Marigold Tansy Prudence Wilhelmina Bettony Dulcie Maud Bess Ottilie Hazel Posy Clemency Ada '
        'Bryony Winnie Lettice Nell Tibby Gwendolyn Agnes Alice Annie Beatrice Betsy Clara Constance Cicely '
        'Daisy Dora Dorothy Edith Elsie Emily Esther Ethel Eliza Fanny Flora Florence Gertie Grace Hannah '
        'Harriet Henrietta Hilda Honor Ivy Jane Jemima Kate Kitty Lavinia Lily Lizzie Lottie Lucy Mabel Martha '
        'Mary Matilda May Meg Mercy Mildred Millie Minnie Molly Nancy Nettie Olive Patience Peggy Phoebe Polly '
        'Primrose Rose Rosie Ruth Sally Sarah Susan Tabitha Temperance Violet Winifred Bella Bertha Effie Edna '
        'Emma Joan Lettie Marjorie Maisie Mattie Nora Pansy Pearl Poppy',
        'Tobin Bram Hob Wendel Barnaby Ambrose Jory Ned Ferris Osgood Pip Cuthbert Dunstan Rollo Jasper Ezekiel '
        'Lem Horace Bartholomew Wilbur Abel Albert Alfred Amos Arthur Barney Basil Ben Bertie Cecil Clement '
        'Edmund Edgar Edwin Eli Ernest Fred Frederick George Gilbert Giles Harry Herbert Hugh Isaac Jack Jacob '
        'Jethro Joe Jonah Josiah Joseph Lewis Luke Matthew Nat Noah Oliver Oswald Percy Peter Reuben Roger '
        'Rufus Sam Seth Silas Simon Stanley Thomas Tom Walter Wat Will Wilfred Bertram Godfrey Humphrey Toby '
        'Archie Alfie Ezra Enoch Obadiah Septimus Benedict Christopher Daniel Felix Gabriel Henry James John '
        'Martin Nicholas Owen Ralph Robert Rowland Stephen',
        'Robin Kit Jem Frankie',
        'Thistlewood Puddifoot Hobbs Mossley Applegarth Wickham Fennimore Crumb Featherstone Tillbrook Underhay '
        'Oakshott Fairweather Cotton Tanner Pickering Dimmock Hobday Gammage Ottley Brewster Cobb Pennington '
        'Ashby Goodbody Littlejohn Shepherd Weaver Hatcher Merriman Appleby Ashworth Baxter Bellamy Birch '
        'Blackmore Bramley Brook Bunting Butterfield Chandler Cherry Cobbold Cotterill Cowley Crabtree Dale '
        'Dewhurst Drinkwater Dunn Fairclough Farley Fenwick Fletcher Foxley Gardner Garland Goodall Goodwin '
        'Hardcastle Hartley Hawthorn Hayward Heron Hickling Hollins Honeyman Hopkins Kettle Lamb Larkin Lovell '
        'Lowe Meadows Merryweather Middleton Miller Nettleton Norbury Oakley Orchard Partridge Peabody Plumb '
        'Pocock Popplewell Puddephat Rook Rowntree Sadler Sawyer Shipley Sparrow Starling Stubbs Swallow '
        'Thackeray Thatcher Tinker Tomkins'),
}

# Victorian and frontier people take given names popular in their birth year too (era_years in
# given_names.py sets the year the story is told), but keep the period family names above.
PERIOD_CULTURES = {
    'victorian': (VICTORIAN, {'english': 'england-wales', 'west-riding': 'england-wales', 'irish': 'ireland',
                              'scottish': 'scotland', 'jewish': 'jewish-diaspora', 'italian': 'italy'}),
    'frontier': (FRONTIER, {'american': 'us', 'mexican': 'mexico', 'cornish': 'england-wales', 'irish': 'ireland',
                            'german': 'germany'}),
}
for bank, links in PERIOD_CULTURES.values():
    for key, culture in links.items():
        bank[key] |= {'cultures': {culture: 1}, 'own_family': True}

# A Roman woman carries her family's name in its feminine form (Julius, Julia).
for roman in ANCIENT_ROME.values():
    roman['feminine_family'] = {'ius': 'ia', 'us': 'a'}

BANKS = {'modern': MODERN, 'victorian': VICTORIAN, 'medieval': MEDIEVAL, 'frontier': FRONTIER, 'storybook': STORYBOOK,
         'edo-japan': EDO_JAPAN, 'qing-china': QING_CHINA, 'ottoman': OTTOMAN, 'ancient-rome': ANCIENT_ROME,
         'mughal-india': MUGHAL_INDIA,
         # Not people of one period but the other peoples of a fantasy world, which a town adds to its own bank with
         # `names.also` and weighs in its mix beside its human heritages (scripts/world/peoples.py).
         'peoples': peoples.bank()}

NAMES = {
    'schema_version': 1,
    'source': {'kind': 'curated', 'title': 'Name banks written for Prospero Dungeon', 'license': 'CC0-1.0',
               'retrieved': '2026-10-05',
               'note': 'Common given and family names by period and heritage, from general knowledge, for fiction. '
                       'Group weights for real cities are rough estimates, not census figures.'},
    'banks': BANKS,
    # The bank a city uses when it names none, and the group weights it starts from.
    'eras': {
        'modern': {'bank': 'modern', 'mix': {'anglo': 4, 'black-american': 1.5, 'hispanic': 2, 'east-asian': 0.7,
                                             'south-asian': 0.5, 'jewish': 0.4, 'italian': 0.5, 'irish': 0.5,
                                             'slavic': 0.3, 'arabic': 0.3, 'west-african': 0.2, 'caribbean': 0.2}},
        # A city in 2077, mixed from the whole world rather than one country.
        'future': {'bank': 'modern', 'mix': {'anglo': 2, 'hispanic': 2.5, 'east-asian': 2.5, 'south-asian': 2,
                                             'black-american': 1.5, 'west-african': 1.5, 'arabic': 1, 'slavic': 0.8,
                                             'caribbean': 0.5, 'italian': 0.4, 'irish': 0.4, 'jewish': 0.3}},
        'other': {'bank': 'modern', 'mix': {}},
        'victorian': {'bank': 'victorian', 'mix': {'english': 8, 'irish': 1.5, 'scottish': 1, 'jewish': 0.6,
                                                   'italian': 0.3}},
        'steampunk': {'bank': 'victorian', 'mix': {'west-riding': 8, 'english': 2, 'irish': 1.5, 'scottish': 0.5}},
        'medieval': {'bank': 'medieval', 'mix': {'english': 6, 'norman': 2, 'welsh': 1}},
        'frontier': {'bank': 'frontier', 'mix': {'american': 6, 'mexican': 3, 'cornish': 1.5, 'irish': 1.5,
                                                 'german': 1, 'chinese': 0.6}},
        'fantasy': {'bank': 'storybook', 'mix': {}},
        # An American city in 1926, after the great migrations from Ireland, Italy, Germany and Eastern Europe
        # and the Great Migration north; born 1860-1908, they take given names from their birth year.
        'jazz-age': {'bank': 'modern', 'mix': {'anglo': 5, 'irish': 1.6, 'german': 1.4, 'italian': 1.2,
                                               'jewish': 0.9, 'slavic': 0.8, 'black-american': 0.9,
                                               'hispanic': 0.15, 'east-asian': 0.1}},
    },
}

if __name__ == '__main__':
    OUT.write_text(json.dumps(NAMES, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    LIFESPANS.write_text(json.dumps(peoples.lifespans(), indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {OUT} and {LIFESPANS}')
