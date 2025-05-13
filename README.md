# RecapAssistant

------ RECAP ASSISTANT FOR DAVINCI RESOLVE ------

--- EESTI KEELES (ENGLISH BELOW) ---

Recap Assistant for DaVinci Resolve on tarkvaraline lahendus mõnda sündmust või ajaperioodi kokkuvõtva video hõlpsasti kokku monteerimiseks. Vajalike kasutajasisendite (sh üks kuni mitu sisendvideofaili, üks sisendhelifail, soovitavad lisaparameetrid) järel täidab automaatselt tarkvara oma põhifunktsionaalsused - sisendfailidest heli tempo ning videote meeleolukate hetkede tuvastamine ja nende põhjal videot monteeriva skripti genereerimine.

--- KASUTUSJUHEND ---
1. Ava RecapAssistantForDaVinciResolve.exe (võtab pisut aega...)
2. Klõpsa nupul '1. Analyse Audio' ning vali helifail oma arvutist. Helianalüüs algab automaatselt
3. Helianalüüsi lõppedes avaneb valik '2. Analyse Video(s)'. Klõpsa sellel nupul ning vali üks või mitu videofaili oma arvutist. Videoanalüüs algab automaatselt
4. Oota, kuna videoanalüüs võtab pisut aega. Selle lõppedes avaneb lühikokkuvõte analüüside tulemustest. Samuti tekivad probleemide korral hüpikaknad, mis kirjeldavad probleemi olemust. Probleemi korral lähtuda kasutajajuhendi 7. sammust ning uuesti proovides välja jätta probleeme tekitanud sisendfaili(d).
5. Vali 'Editing Style*' rippmenüüst endale sobiv monteerimisstiil - relaxed on rahulikum stiil, standard on tavapärane stiil ning fast-paced on kiiremas tempos stiil.
6. Stiili valides avaneb valik 'Create Script' - klõpsa sellel ning salvesta skript suvalisse kausta VÕI otse DaVinci Resolve skriptide kausta (sellest lähemalt allpool)

Ja skript ongi kasutamiseks valmis! Siin on paar lisanduvat sammu, mis ei ole kohustuslikud, kuid on hea teada:

7. Soovi korral on võimalik mistahes sammu ajal klõpsata nupule 'Reset', et kasutajaliides lähtestada ning uuesti alustada (NB! Hetkeversioonis ei lõpeta 'Reset' nupule klõpsamine taustaprotsessi - mõne suurema analüüsi tühistamise puhul on ehk mõistlik programm siiski taaskäivitada)
8. Soovi korral on analüüsi lõppedes kasutajal salvestada CSV-formaadis kokkuvõte analüüsi tulemustest klõpsates nupul 'Save CSV'. Salvesta see mistahes kausta.

--- KUIDAS LEIDA DAVINCI RESOLVE SKRIPTIDE KAUSTA? ---
DaVinci Resolve skriptide kaust asub reeglina aadressil:

C:\Users\<TEIE KASUTAJA>\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility

Kuna AppData on peidetud kaust, on lihtsaim viis sellele ligi pääsemiseks otsida Windowsi otsingust (tegumiribal vasakul, Windows logo kõrval) '%appdata%' ning avada esimene otsingutulemus.

Alternatiivne skriptide kaust asub aadressil:
C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility

Kuna ProgramData on peidetud kaust, pääseb sellele sarnaselt ligi: otsi Windowsi otsingus '%programdata%'.

--- KUIDAS KASUTADA SKRIPTI DAVINCI RESOLVE TARKVARA SEES? ---
1. Ava DaVinci Resolve
2. Klõpsa nupul 'New Project', et avada uus projekt VÕI ava olemasolev projekt
3. Ava ülevalt tööriistaribalt rippmenüü 'Workspace' --> 'Scripts' --> Vali enda skript tekkinud hõljukboksist.
4. Skript peaks automaatselt lugema sisse sisendfailid ning kokku panema ajajoone. Skripti tööd saab jälgida konsoolist, mille saab avada valides 'Workspace' --> 'Console'
5. Siinkohal võib soovi korral tutvuda ajajoonega, tõsta klippe ümber, lisada efekte ning sooritada muid monteerimistoiminguid
6. Kui video on valmis, saab valida ülevalt paremalt alamtööriistaribalt valiku 'Quick Export' ning valida omale meelepärase väljundi. Video salvestatakse kasutaja valitud kausta.



--- IN ENGLISH ---

Recap Assistant for DaVinci Resolve is a software solution for easily assembling a video summarizing an event or time period. After the necessary user inputs (including one to several input video files, one input audio file, additional parameters), the software performs its main functions - identifying the audio tempo and valuable moments in the videos from the input files and generating a video editing script based on them.

--- USER INSTRUCTIONS ---
1. Open RecapAssistantForDaVinciResolve.exe (takes a little while...)
2. Click the '1. Analyze Audio' button and select an audio file from your computer. The audio analysis will begin automatically
3. When the audio analysis is complete, the '2. Analyzing video(s)' option will become available. Click on this button and select one or more video files from your computer. The video analysis will begin automatically
4. Wait, as the video analysis will take some time. When it is finished, a brief summary of the analysis results will open. In case of any problems, pop-up windows will appear that describe the nature of the problem. In case of any problems, follow step 7 of the user instructions and try again without the input file(s) that caused the problem
5. Select the editing style that suits you from the 'Editing Style*' drop-down menu
6. When you select a style, the 'Create Script' option will open - click on it and save the script to any folder OR directly to the DaVinci Resolve scripts folder (more on this below)

And the script is ready to use! Here are a few additional steps that are not mandatory yet perhaps still useful:

7. You can click the 'Reset' button at any time to reset the user interface and start over (NB! In the current version, clicking the 'Reset' button does not stop the background process - for longer analyses, it may be best to close and re-open the program)
8. If desired, at the end of the analysis, the user can save a summary of the analysis results in CSV format by clicking the 'Save CSV' button. Save it to any folder.

--- HOW TO FIND THE DAVINCI RESOLUTION SCRIPT FOLDER? ---
The DaVinci Resolve scripts folder is usually located at:

C:\Users\<YOUR USER>\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility

Since AppData is a hidden folder, the easiest way to access it is to search for '%appdata%' in Windows Search (on the taskbar on the left, next to the Windows logo) and open the first search result.

The alternative scripts folder is located at:
C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility

Since ProgramData is a hidden folder, it can be accessed similarly: search for '%programdata%' in Windows search.

--- HOW TO USE A SCRIPT WITHIN DAVINCI RESOLVE SOFTWARE? ---
1. Open DaVinci Resolve
2. Click on the 'New Project' button to open a new project OR open an existing project
3. Open the 'Workspace' drop-down menu from the top toolbar --> 'Scripts' --> Select your script from the hover box.
4. The script should read the user input files and assemble the timeline. The script's process can be followed from the Workspace console, which can be opened by selecting 'Workspace' --> 'Console'
5. Now, you can view the timeline, move clips around, add effects, and perform other editing operations if desired.
6. When the video is ready, you can select 'Quick Export' from the sub-toolbar at the top right and choose the output you prefer. The video will be saved to the folder selected by the user.
