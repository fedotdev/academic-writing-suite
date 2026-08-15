-- Добавляет видимые чёрные границы ко всем таблицам (ГОСТ 7.32-2017 п. 6.6)
function Table(tbl)
  local borders = pandoc.RawBlock('openxml', '<w:tblBorders>'
    .. '<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    .. '<w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    .. '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    .. '<w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    .. '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    .. '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    .. '</w:tblBorders>')
  tbl.attributes = tbl.attributes or pandoc.Attr()
  return tbl
end
