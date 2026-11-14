import dev.ftb.mods.ftblibrary.snbt.SNBT;
import dev.ftb.mods.ftblibrary.util.TextComponentParser;
import dev.ftb.mods.ftbquests.quest.translation.TranslationTable;
import dev.ftb.mods.ftbquests.quest.translation.TranslationKey;
import dev.ftb.mods.ftbquests.client.ClientQuestFile;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.StringTag;
import net.minecraft.network.chat.Component;
import net.minecraft.SharedConstants;
import net.minecraft.server.Bootstrap;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Path;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Stream;
import com.google.gson.JsonParseException;

/** Uses the FTB parser and translation tables from the shipped game. */
class VerifyQuestTranslation {
    public static void main(String[] args) throws Exception {
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        CompoundTag english = SNBT.tryRead(Path.of(args[0]));
        CompoundTag russian = SNBT.tryRead(Path.of(args[1]));
        require(english.getAllKeys().equals(russian.getAllKeys()), "Quest translation keys differ");
        var englishTable = TranslationTable.fromNBT(english);
        var russianTable = TranslationTable.fromNBT(russian);
        require(englishTable.size() == english.size() && russianTable.size() == russian.size(),
                "FTB translation table lost keys");
        // The public parser turns format exceptions into visible red text.
        Method strictParser = TextComponentParser.class.getDeclaredMethod("parse");
        strictParser.setAccessible(true);
        var constructor = TextComponentParser.class.getDeclaredConstructor(String.class, Function.class);
        constructor.setAccessible(true);
        Function<String, Component> substitutes = Component::literal;
        var registries = HolderLookup.Provider.create(Stream.empty());
        int strings = 0;
        int jsonComponents = 0;
        int sourceFormatErrors = 0;
        for (String key : english.getAllKeys().stream().sorted().toList()) {
            require(english.get(key).getId() == russian.get(key).getId(), "Different value type: " + key);
            List<String> source;
            List<String> translated;
            if (english.get(key) instanceof StringTag) {
                source = List.of(englishTable.getStringTranslation(key).orElseThrow());
                translated = List.of(russianTable.getStringTranslation(key).orElseThrow());
            } else {
                require(english.get(key) instanceof ListTag, "Unexpected value type: " + key);
                source = englishTable.getStringListTranslation(key).orElseThrow();
                translated = russianTable.getStringListTranslation(key).orElseThrow();
            }
            require(source.size() == translated.size(), "Different paragraph count: " + key);
            for (int index = 0; index < source.size(); index++) {
                String original = source.get(index);
                String translation = translated.get(index);
                require(original.isBlank() == translation.isBlank(), "Different paragraph layout: " + key);
                if (jsonComponent(original, registries)) {
                    require(jsonComponent(translation, registries), "Invalid translated JSON component: " + key);
                    jsonComponents++;
                    strings++;
                    continue;
                }
                boolean sourceAccepted = parses(strictParser, constructor.newInstance(original, substitutes));
                boolean translationAccepted = parses(strictParser, constructor.newInstance(translation, substitutes));
                require(translationAccepted || !sourceAccepted, "New FTB text parser error at " + key + "/" + index);
                sourceFormatErrors += translationAccepted ? 0 : 1;
                strings++;
            }
        }
        System.out.printf("keys=%d strings=%d jsonComponents=%d inheritedFormatErrors=%d%n",
                russianTable.size(), strings, jsonComponents, sourceFormatErrors);
        if (args.length > 2) {
            var file = new ClientQuestFile();
            var manager = file.getTranslationManager();
            manager.loadFromNBT(file, Path.of(args[2]));
            String title = "file.0000000000000001.title";
            require(manager.getStringTranslation(file, "ru_ru", TranslationKey.TITLE)
                    .equals(russianTable.getStringTranslation(title)), "FTB did not select the Russian title");
            require(manager.getStringTranslation(file, "en_us", TranslationKey.TITLE)
                    .equals(englishTable.getStringTranslation(title)), "FTB did not select the English title");
            var chinese = TranslationTable.fromNBT(SNBT.tryRead(Path.of(args[2], "zh_cn.snbt")));
            require(manager.getStringTranslation(file, "zh_cn", TranslationKey.TITLE)
                    .equals(chinese.getStringTranslation(title)), "FTB did not select the Chinese title");
            System.out.println("FTB locale lookup: ru_ru, en_us, zh_cn");
        }
    }

    private static boolean jsonComponent(String text, HolderLookup.Provider registries) {
        String trimmed = text.trim();
        if (!(trimmed.startsWith("{") && trimmed.endsWith("}") ||
                trimmed.startsWith("[") && trimmed.endsWith("]"))) return false;
        try {
            return Component.Serializer.fromJson(trimmed, registries) != null;
        } catch (JsonParseException ignored) {
            return false;
        }
    }

    private static boolean parses(Method parser, Object instance) throws Exception {
        try {
            parser.invoke(instance);
            return true;
        } catch (InvocationTargetException failure) {
            if (!(failure.getCause() instanceof Exception)) throw failure;
            return false;
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalStateException(message);
    }
}
