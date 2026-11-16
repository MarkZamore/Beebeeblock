// Set the vanilla option before the title menu initializes.
const $LanMinecraftTitleScreen = Java.loadClass('net.minecraft.client.gui.screens.TitleScreen')
const $LanMinecraftScreenInit = Java.loadClass('net.neoforged.neoforge.client.event.ScreenEvent$Init$Pre')

NativeEvents.onEvent($LanMinecraftScreenInit, event => {
  if (event.getScreen() instanceof $LanMinecraftTitleScreen) {
    Client.options.skipMultiplayerWarning = true
  }
})
