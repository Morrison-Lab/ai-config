# Parse every data file you change

Parse every data file a change touches with a real parser before calling a PR ready or reporting a head as final:
a CSV with a CSV reader (every row's field count equals the header's),
and YAML and JSON by loading them.

Reading a row beside its neighbours is not a check:
an unquoted comma in `courses.csv` made a row five fields wide on Morrison-Lab/lds#2220,
and two review rounds repeated "same four columns" until a third parsed the file (ai-config#5206).
