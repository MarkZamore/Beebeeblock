# Beebeeblock - The Skyhive

Подготовка сборки 3.07.8 для LANMinecraft. [Авторский клиентский выпуск](https://www.curseforge.com/minecraft/modpacks/beebeeblock-the-skyhive/files/9310908)

`tools/upstream-client-lock.json` фиксирует SHA256 и размер оригинального ZIP, ссылки на официальный источник, записи зависимостей и SHA256 файлов внутри авторских overrides. Minecraft и загрузчик взяты из оригинального манифеста. Java в `portable-pack.json` соответствует выбору текущего лаунчера для этой версии Minecraft и проверяется при запуске.

## Восстановление авторского клиента

Из корня LANMinecraft используйте `tools/PackData/CurseForge/prepare.py` с `--project-id 1479709` и `--file-id 9310908`. Укажите этот lock через `--expect` и новый каталог внутри своего стенда через `--output`. Полная подготовка проверяет все заявленные зависимости. Отдельный lock поставки и метаданные карточки готовятся после запуска и проверки фактического состава.

## Публикация

All Rights Reserved. Разрешение на публикацию авторского состава через GitHub Releases не подтверждено.
