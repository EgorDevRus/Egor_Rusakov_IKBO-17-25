# Задача 1
```bash
grep "" passwd | cut -d ":" -f1 | sort
```

# Задача 2
```bash
cat /etc/protocols | grep -v '^#' | awk 'NF {print $2, $1}' | sort -nr | head -n 5
```
# Задача 3
```bash
#!/usr/bin/env bash

text="$*"
len=$(( ${#text} + 2 ))
line=$(printf '%*s' "$len" '' | tr ' ' '-')
echo "+$line+"
echo "| $text |"
echo "+$line+"
```
# Задача 4
```bash
#!/usr/bin/env bash
grep -o '[A-Za-z_][A-Za-z0-9_]*' "$1" | sort -u | tr '\n' ' '
echo ""
```
# Задача 5
```bash
#!/usr/bin/env bash

src="$1"

chmod +x "$src" 

cp "$src" /usr/local/bin/
```

# Задание 6
```bash
#!/usr/bin/env bash
for file in *.{c,js,py}; do
    [ -e "$file" ] || continue
    first_line=$(head -n 1 "$file")
    if echo "$first_line" | grep -qE '^(\/\/|\/\*|#)'; then
        echo "$file"
    fi
done
```

# Задание 7 
```bash
#!/usr/bin/env bash

find "$1" -type f -exec md5sum {} + | sort | uniq -w32 -D
```

# Задание 8
```bash
#!/usr/bin/env bash
find . -name "*.$1" | xargs tar -cvf "$2"

```
# Задание 9
```bash
#!/usr/bin/env bash
input="$1"

output="$2"

sed 's/    /\t/g' "$input" > "$output"
```

# Задание 10
```bash
#!/usr/bin/env bash
find "$1" -type f -empty
```
