<?xml version="1.0" encoding="UTF-8"?>
<!--
This file is part of JuliaBase, the samples database.

Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
                      Marvin Goblet <m.goblet@fz-juelich.de>,
                      Torsten Bronger <t.bronger@fz-juelich.de>

You must not use, install, pass on, offer, sell, analyse, modify, or
distribute this software without explicit permission of the copyright holder.
If you have received a copy of this software without the explicit permission
of the copyright holder, you must destroy it immediately and completely.
-->

<xsl:stylesheet xmlns:atom="http://www.w3.org/2005/Atom" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">

<xsl:output method="html"/>

<xsl:template match="/atom:feed">
<html>
  <head>
    <title><xsl:value-of select="atom:title"/></title>
  </head>

  <body>
    <h1><xsl:value-of select="atom:title"/></h1>
    <p>Last update: <xsl:value-of select="atom:updated"/></p>

    <xsl:for-each select="atom:entry">
      <h2>
        <xsl:choose>
          <xsl:when test="atom:link">
            <a href="{atom:link/@href}"><xsl:value-of select="atom:title"/></a>
          </xsl:when>
          <xsl:otherwise>
            <xsl:value-of select="atom:title"/>
          </xsl:otherwise>
        </xsl:choose>
      </h2>
      <p><xsl:value-of select="atom:updated"/></p>

      <div class="content">
        <xsl:value-of select="atom:content" disable-output-escaping="yes"/>
      </div>
    </xsl:for-each>
  </body>
</html>
</xsl:template>

</xsl:stylesheet>
