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
===============================

Der „Chantal Remote-Client“ ist ein kleines Programm, das es ermöglicht, von
einem beliebigen Computer des Instituts Daten in die Datenbank automatisiert
einzutragen (und auszulesen).

Warum das ganze?  Damit man an Apparaturen, an denen das sinnvoll ist, die
Daten, die dort produziert werden und die für die Datenbank interessant sind,
in dieselbe hineinschreiben kann, ohne daß der Operateur noch mal im Browser
die ganzen Daten abtippen muß.  Denn letzteres ist umständlich und
fehleranfällig.

.. toctree::
   :maxdepth: 2


Das Problem
---------------

Die Datenbank ist nur sinnvoll, wenn da auch alle relevanten Daten drinstehen.
Die beste Möglichkeit, die Datenbank fehlerfrei und vollständig zu halten ist,
daß die datengenerierenden System (Depositionen, Meßapparaturen) automatisch
die Daten an die Datenbank übermitteln.

Nur wie?  Der Browser schickt Daten an die Datenbank über das HTTP-Protokoll.
Und das ist auch das einzige Tor zur Datenbank, damit alle Daten an denselben
Überprüfungen und Authentifizierungen vorbei müssen.  Also müssen die
(Meß-)Systeme ihre Daten ebenso über HTTP an den Datenbank-Server schicken.

Das führt zu zwei Problemen:

#. Die Programmierer im Institut wissen nicht, wie sie Daten per HTTP
   verschicken.  (Ist ja auch keine besonders aufregende Erfahrung ...)

#. Nicht alle Programmiersprachen und Systeme im IEF *können* überhaupt Daten
   per HTTP verschicken.

Im Institut kommen sehr verschiedene Programmiersysteme zum Einsatz: HT Basic,
LabVIEW, Delphi, Python etc.  Außerdem gibt es Systeme, zu denen wir nicht den
Quellcode haben, die aber u. U. eine eingebaute Makro- oder Skriptsprache
haben.  Die müssen nun alle in die Lage versetzt werden, in *einfacher* Form
Daten an den Datenbank-Server zu schicken, und eventuell sogar Daten aus der
Datenbank auszulesen.


Die Lösung
--------------

Alle Systeme und alle Programmierer im IEF sollten zumindest zwei Sachen
können:

#. Daten in eine Textdatei schreiben bzw. aus ihr lesen.

#. Ein externes, rein kommandozeilenbasiertes Programm ausführen.

Und mehr ist für den Chantal Remote-Client nicht nötig!

Will man also aus einem Programm heraus Daten an die Datenbank senden, muß auf
dem jeweiligen Rechner zunächst der Remote-Client installiert sein.  Dann
schreibt man seine „Wunschliste“ in eine Textdatei und ruft ein bestimmtes
externes Programm auf.  Anschließend kann man in einer Log-Datei sehen, ob
alles glattgegangen ist.  Die Log-Datei sollte man natürlich auch durch das
eigene Programm auslesen lassen.


Installation des Remote-Clients
------------------------------------

To be done ...


Grundlegendes
------------------

Technisch gesehen ist die Textdatei, die man schreiben muß, ein
Python-Programm.  Python ist eine höhere Programmiersprache.  Das, was man zum
übermitteln benötigt, ist zwar so einfach, daß man kaum merkt, daß man
irgendwas programmiert, aber theoretisch steht einem der komplette Sprachschatz
von Python zur Verfügung.

Eine Datei für den Remote-Client beginnt immer mit

::

    from chantal_remote import *

Das bedeutet, daß alle Funktionen des Moduls ``chantal_remote`` eingebunden
werden.

In Python ist die Einrückung der Zeilen wichtig.  Achtet deshalb darauf, daß
alle neuen Befehle in der ersten Spalte beginnen.  Solltet ihr Sonderzeichen
(deutsche Umlaute o. ä.) brauchen, kontaktiert mich.

Alle Zeilen, die mit einer Raute ``#`` beginnen, werden als
Kommentarzeilen ignoriert::

    # Programm zum uebersenden von 6-Kammer-Depositionen
    from chantal_remote import *


Einloggen und ausloggen
.......................

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
Wenn man es lokal auf seinem Rechner tut und die Datei danach wieder löscht,
ist das okay.  An einer Meßapparatur, zu der niemand sonst Zugriff hat, mag das
auch okay sein.  Man muß aber, wenn man die Apparaur an jemanden anderes
übergibt, sein Paßwort löschen.

Besser ist es jedoch, daß das Meßprogramm verlangt, daß man ein Paßwort
eingibt, und die Textdatei, in der das Paßwort dann steht, sofort nach Gebrauch
wieder löscht.  Noch sicherer ist es, gar nicht erst eine Textdatei zu
schreiben, sondern den Text direkt dem Python-Interpreter zu übergeben.  Das
geht aber u. U. nicht mit jeder Programmiersprache.

Außerdem besteht die Möglichkeit, Sammel-Benutzer anzulegen, die mit einem
schwachen Paßwort, das einer begrenzten Zahl von Leuten bekannt ist,
ausgestattet sind.  Zum Beispiel könnte eine Datei so anfangen::

    from chantal_remote import *
    login("pds_benutzer", "rotesocke")


Zeitstempel
...........

An vielen Stellen muß oder kann man sogenannte Zeitstempel angeben.  Das sind
Strings, die angeben, wann ein Prozeß durchgeführt wurde.  Sowas wird
grundsätzlich immer in der Form

::

    "JJJJ-MM-TT HH:MM:SS"

angegeben, also z. B. ``"2008-08-23 13:34:00"``.


Referenz
-----------

Was folgt, ist eine Auflistung aller bislang unterstützter Operationen anhand
von Beispielen.


Proben hinzufügen
.................

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


6-Kammer-Depositionen
.....................

::

    samples = new_samples(5, "6-Kammer-Labor")

    deposition = SixChamberDeposition(samples)
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

    deposition.submit()

Okay, was passiert hier?

* In Zeile 1 hole ich mir 5 neue Proben.  Da ich mit den Proben noch was
  vorhabe, speichere ich sie in der Variablen ``samples``.

* Dann erzeuge ich eine neue 6-Kammer-Deposition in Zeile 3 mit
  ``SixChamberDeposition``, übergebe ihr die Proben als Parameter und speichere
  sie in einer Variablen.

* In Zeile 4 kann man sehen, wie man einem Objekt Eigenschaften zuweist:
  Nämlich mit der beliebten Punkt-Notation.  Mit ``.timestamp = ...`` kann man
  beispielsweise der Deposition einen Zeitstempel aufdrücken.

* Eine Deposition braucht mindestens eine Schicht.  Die legen wir in Zeile 6
  an.  Man muß ihr die Depositions-Variable übergeben, zu der sie gehört.  In
  Zeile 7 weisen wir ihr eine Kammer zu.

* In Zeile 9 legen wir den ersten Channel an und verbinden ihn mit der Schicht,
  analog zu vorhin.  Außerdem weisen wir dem neuen Channel ein paar Attribute
  zu.

* Damit's nicht zu langweilig ist, kommt in Zeile 14 noch ein Channel zu
  derselben Schicht hinzu.

* Schließlich wird in Zeile 19 die Deposition mit allen Schichten und Channels
  in die Datenbank übertragen.
