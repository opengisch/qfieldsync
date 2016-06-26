pyside-lupdate -verbose qfield_sync_py.pro # this parses the py files but not the ui files
lupdate -pro qfield_sync_ui.pro # this parses the ui files, but not the py files
# now need to merge those in one translation file
lconvert -i i18n/QFieldSync_de_ui.ts i18n/QFieldSync_de_py.ts -o i18n/QFieldSync_de.ts
lrelease i18n/QFieldSync_de.ts
