<?xml version="1.0"?>

<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:saxon="http://icl.com/saxon"
  xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
  xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:date="http://exslt.org/dates-and-times"
  extension-element-prefixes="saxon date">

<xsl:output method="text" indent="no" encoding="utf-8"/>

<xsl:variable name="styles-with-topline">
  <xsl:for-each select="//style:style[style:table-cell-properties[@fo:border-top and @fo:border-top != 'none']]">
    <xsl:value-of select="concat('&#34;', @style:name, '&#34;')"/>
  </xsl:for-each>
</xsl:variable>

<xsl:variable name="styles-with-bottomline">
  <xsl:for-each select="//style:style[style:table-cell-properties[@fo:border-bottom and @fo:border-bottom != 'none']]">
    <xsl:value-of select="concat('&#34;', @style:name, '&#34;')"/>
  </xsl:for-each>
</xsl:variable>

<xsl:template match="office:document-content">
  <xsl:variable name="samples">
    <xsl:apply-templates select="descendant::table:table-row"/>
  </xsl:variable>
</xsl:template>

<xsl:template match="table:table-row">
  <xsl:variable name="topline">
    <xsl:for-each select="table:table-cell/@table:style-name">
      <xsl:if test="contains($styles-with-topline, concat('&#34;', string(), '&#34;'))">
        <xsl:text>.</xsl:text>
      </xsl:if>
    </xsl:for-each>
    <xsl:for-each select="preceding-sibling::table:table-row[position() = 1]/table:table-cell/@table:style-name">
      <xsl:if test="contains($styles-with-bottomline, concat('&#34;', string(), '&#34;'))">
        <xsl:text>.</xsl:text>
      </xsl:if>
    </xsl:for-each>
  </xsl:variable>
  <xsl:if test="string-length($topline) > 0">
    <xsl:text>................................................................................&#10;</xsl:text>
    <xsl:text>................................................................................&#10;</xsl:text>
    <xsl:text>................................................................................&#10;</xsl:text>
  </xsl:if>
  <xsl:apply-templates select="table:table-cell"/>
  <xsl:text>&#10;</xsl:text>
</xsl:template>

<xsl:template match="text:p">
  <xsl:value-of select="concat(., '&#9;')"/>
</xsl:template>

</xsl:stylesheet>
