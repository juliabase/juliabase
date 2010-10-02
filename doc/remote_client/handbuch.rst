.. Remote-Client documentation master file, created by sphinx-quickstart on Mon Jan 12 16:20:00 2009.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. This file is part of Chantal, the samples database.
..
.. Copyright (C) 2010 Forschungszentrum Jülich, Germany,
..                    Marvin Goblet <m.goblet@fz-juelich.de>,
..                    Torsten Bronger <t.bronger@fz-juelich.de>
..
.. You must not use, install, pass on, offer, sell, analyse, modify, or
.. distribute this software without explicit permission of the copyright
.. holder.  If you have received a copy of this software without the explicit
.. permission of the copyright holder, you must destroy it immediately and
.. completely.


.. highlight:: python
   :linenothreshold: 10

Der Chantal Remote-Client
====================================

Der „Chantal Remote-Client“ ist eine Programm-Bibliothek, die es ermöglicht,
von einem beliebigen Computer des Instituts Daten in die Datenbank
automatisiert einzutragen und auszulesen.

Warum das ganze?  Damit man an Apparaturen, an denen das sinnvoll ist, die
Daten, die dort produziert werden und die für die Datenbank interessant sind,
in dieselbe hineinschreiben kann, ohne daß der Operateur noch mal im Browser
die ganzen Daten abtippen muß.  Denn das wäre umständlich und fehleranfällig.
Außerdem müssen einige Apparaturen Daten aus der Datenbank auslesen,
z.B. Schichtdicken und Kontaktgeometrien.

Darüberhinaus soll es Mitarbeitern ermöglicht werden, mit selbstgeschriebenen
Programmen Daten aus der Datenbank auszulesen, um sie irgendwie
weiterzuverarbeiten, beispielsweise um sie statistisch auszuwerten oder zu
plotten.  Die Ergebnisse können ihrerseits wieder in die Datenbank
zurückgeschrieben werden.

.. toctree::
   :maxdepth: 2


Das Problem
-----------------

Okay, die Motivation sollte klar sein.  Aber wie soll das realisiert werden?
Der Browser schickt Daten an die Datenbank über das HTTP-Protokoll.  Zum
HTTP-Protokoll gibt es keine Alternative.  Also müssen die (Meß-)Systeme ihre
Daten ebenso über HTTP an den Datenbank-Server schicken.

Das führt zu zwei Problemen:

#. Die Programmierer im Institut haben keine Erfahrung mit dem HTTP-Protokoll.

#. Die Verwendung von HTTP ist in vielen Programmiersprachen umständlich.
   Schlimmer noch: Nicht alle Programmiersprachen und Systeme im IEF *können*
   überhaupt Daten per HTTP verschicken.

Im Institut kommen sehr verschiedene Programmiersysteme zum Einsatz: HTBasic,
LabVIEW, Delphi, VisualBasic etc.  Außerdem gibt es Systeme, zu denen wir nicht
den Quellcode haben, die aber u. U. eine eingebaute Makro- oder Skriptsprache
haben.  Die müssen nun alle in die Lage versetzt werden, in einfacher Form
Daten an den Datenbank-Server zu schicken, und eventuell sogar Daten aus der
Datenbank auszulesen.


Die Lösung
---------------

Alle Systeme und alle Programmierer im IEF sollten zumindest zwei Sachen
können:

#. Daten in eine Textdatei schreiben bzw. aus ihr lesen.

#. Ein externes, rein kommandozeilenbasiertes Programm ausführen.

Und mehr ist für den Chantal Remote-Client nicht nötig!

Will man also aus einem Programm heraus Daten an die Datenbank senden, schreibt
man diese Daten in eine Textdatei und ruft ein bestimmtes externes Programm
auf.  Anschließend kann man in einer Log-Datei sehen, ob alles glattgegangen
ist.  Die Log-Datei sollte man natürlich auch durch das eigene Programm
auslesen lassen.

Die meisten Programmiersprachen (ich kann es sicher von Delphi und LabVIEW
sagen) erlauben sogar, daß die Daten direkt an das aufgerufene Programm
übermittelt wird und so eine extra Textdatei unnötig wird.

Der Gipfel der Bequemlichkeit existiert zur Zeit nur für Delphi: Ich habe eine
kurze Delphi-Unit geschrieben, die den Remote-Client ansteuert.  Das Arbeiten
mit der Datenbank gestaltet sich dann sehr ähnlich zum Ansteuern eines
Meßinstruments: Man schickt eine Befehlskette hin und bekommt eine Antwort
(oder eine Fehlermeldung) zurück.

Ziel ist, daß solche Anbindungen auch für LabVIEW, HTBasic und VisualBasic
gebaut werden.


Installation des Remote-Clients
------------------------------------------

Im allgemeinen muß der Remote-Client nicht installiert werden.  Er steht auf
einem für alle lesbaren freigegeben Verzeichnis zur Verfügung.


Grundlegendes
--------------------

Technisch gesehen ist die Textdatei, die man schreiben muß, ein
Python-Programm.  Python ist eine höhere Programmiersprache.  Sie ist einfach
genug, daß man sie nicht beherrschen muß, um den Remote-Client zu benutzen.

Eine Datei für den Remote-Client beginnt immer mit

::

    from chantal_remote import *

Das bedeutet, daß alle Funktionen des Moduls ``chantal_remote`` eingebunden
werden.

Achtet darauf, daß alle Zeilen in der ersten Spalte beginnen, es sei denn, sie
setzen eine vorangehende Zeile fort.  Alle Zeilen, die mit einer Raute ``#``
beginnen, werden als Kommentarzeilen ignoriert.

Man kann auch alles in eine einzige Zeile schreiben.  Dann muß man die
Anweisungen mit Semikolons trennen.  Das ist interessant, wenn man viele
Anweisungen in einem Befehlsstring unterbringen muß.


Einloggen und ausloggen
.....................

Es ist wichtig, sich beim Server zu identifizieren.  Dazu muß man sich zu
Beginn der Datei einloggen und sich zuletzt auch wieder ausloggen::

    from chantal_remote import *

    login("r.meier", "mammaistdiebeste")

    # Hier nun die ganzen Daten ...

    logout()

Dabei ist ``"r.meier"`` der Loginname und ``"mammaistdiebeste"`` das Paßwort.
Beides ist dasselbe wie für die freigegebenen Verzeichnissen und Drucker im
Institut.  Im folgenden geht es nun darum, wie man die Daten selber angibt.

Ein Wort zu Paßworten.  Sie sollte man nicht leichtfertig in Dateien schreiben.
Wenn die Hauptprogrammiersprache es zuläßt (z.B. Delphi), sollte man gar keine
Datei schreiben, sondern Pipes und Programmargumente benutzen.  Wenn man um
eine Datei mit Paßworten nicht herumkommt, muß man unbedingt dafür sorgen, daß
diese Datei nach Gebrauch sofort wieder gelöscht wird.


Zeitstempel
..........

An vielen Stellen muß oder kann man sogenannte Zeitstempel angeben.  Das sind
Strings, die angeben, wann ein Prozeß durchgeführt wurde.  Sowas wird
grundsätzlich immer in der Form

::

    "JJJJ-MM-TT HH:MM:SS"

angegeben, also z. B. ``"2008-08-23 13:34:00"``.


Referenz
------------

Was folgt, ist eine Auflistung aller bislang unterstützter Operationen anhand
von Beispielen.


Proben hinzufügen
................

Man kann bis zu 100 Proben auf einen Schlag hinzufügen.  Der folgende Befehl
legt 10 neue Proben an und gibt an, daß sie zur Zeit im MAIKE-Labor liegen::

    from chantal_remote import *
    login("r.meier", "mammaistdiebeste")
    new_samples(10, "MAIKE-Labor")
    logout()

Es gibt noch einige optionale Parameter, nämlich Substrat, Zeitstempel, Zweck,
Tags und Gruppe, bzw. ``substrate``, ``timestamp``, ``purpose``, ``tags`` und
``topic``.  Man könnte also auch schreiben::

    new_samples(10, "MAIKE-Labor",
		substrate="asahi-u",
		timestamp="2008-08-23 13:34:00",
		topic="SiC")

Aber ``"asahi-u"`` ist eh Default, und wenn kein Zeitstempel angegeben wird,
gilt *jetzt*.  Bei optionalen Parametern schreibt man besser den Parameternamen
mit Gleichheitszeichen davor.

Ganz wichtig: Alle so angelegten Proben haben einen provisorischen Namen (also
Stern + Nummer).


6-Kammer-Depositionen
....................

::

    sample_ids = new_samples(5, "6-Kammer-Labor")

    deposition = SixChamberDeposition()
    deposition.sample_ids = sample_ids
    deposition.timestamp = "2008-09-15 22:29:00"

    layer = SixChamberLayer(deposition)
    layer.chamber = "#1"

    channel1 = SixChamberChannel(layer)
    channel1.number = 1
    channel1.gas = "SiH4"
    channel1.flow_rate = 1

    channel2 = SixChamberChannel(layer)
    channel2.number = 2
    channel2.gas = "SiH4"
    channel2.flow_rate = 2

    deposition_number = deposition.submit()

Okay, was passiert hier?

* In Zeile 1 hole ich mir 5 neue Proben.  Da ich mit den Proben noch was
  vorhabe, speichere ich sie in der Variablen ``samples``.

* Dann erzeuge ich eine neue 6-Kammer-Deposition in Zeile 3 mit
  ``SixChamberDeposition``, übergebe ihr die Proben als Parameter und speichere
  sie in einer Variablen.

* In Zeile 4 kann man sehen, wie man einem Objekt Eigenschaften zuweist:
  Nämlich mit der beliebten Punkt-Notation.  Mit ``.timestamp = ...`` kann man
  beispielsweise der Deposition einen Zeitstempel aufdrücken.

* Eine Deposition braucht mindestens eine Schicht.  Die legen wir in Zeile 7
  an.  Man muß ihr die Depositions-Variable übergeben, zu der sie gehört.  In
  Zeile 8 weisen wir ihr eine Kammer zu.

* In Zeile 10 legen wir den ersten Channel an und verbinden ihn mit der
  Schicht, analog zu vorhin.  Außerdem weisen wir dem neuen Channel ein paar
  Attribute zu.

* Damit's nicht zu langweilig ist, kommt in Zeile 15 noch ein Channel zu
  derselben Schicht hinzu.

* Schließlich wird in Zeile 20 die Deposition mit allen Schichten und Channels
  in die Datenbank übertragen.  Die dabei entstehende Depositionsnummer wird in
  der Variablen ``deposition_number`` gespeichert.


Umbenennen nach Deposition
.........................

Die Proben haben nach dem Übertragen der Deposition immer noch ihre alten
Namen.  Allerdings ist es im Institut ja üblich, daß die Probe nach der
Deposition die Depositionsnummer annimmt.  Dafür gibt es
``rename_after_deposition``::

    new_names = {sample_ids[0]: deposition_number + "-1",
                 sample_ids[1]: deposition_number + "-2",
		 sample_ids[2]: deposition_number + "-3",
		 sample_ids[3]: deposition_number + "-4",
		 sample_ids[4]: deposition_number + "-5"}
    rename_after_deposition(deposition_number, new_names)

``new_names`` ist dabei ein sogenanntes „Dictionary“, das die Proben-IDs der
fünf Proben (vor den Doppelpunkten) auf ihre neuen Namen (nach den
Doppelpunkten) abbildet.  Man beachte, daß in Arrays die Indizierung bei Null
beginnt.
