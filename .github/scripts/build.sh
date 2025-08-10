#!/usr/bin/env bash
zip opa.zip *.py
mv opa.zip opa.pyz
echo '#!/usr/bin/env python3' | cat - opa.pyz > opa
cp opa opa.pyz
chmod +x opa
chmod +x opa.pyz
./opa --help
./opa.pyz --version