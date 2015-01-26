<?xml version="1.0" encoding="UTF-8"?>
<!--
This file is part of JuliaBase, see http://www.juliabase.org.
Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
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
