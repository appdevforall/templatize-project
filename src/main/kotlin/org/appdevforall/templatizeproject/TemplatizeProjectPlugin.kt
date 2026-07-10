package org.appdevforall.templatizeproject

import com.itsaky.androidide.plugins.IPlugin
import com.itsaky.androidide.plugins.PluginContext
import com.itsaky.androidide.plugins.extensions.DocumentationExtension
import com.itsaky.androidide.plugins.extensions.EditorTabExtension
import com.itsaky.androidide.plugins.extensions.EditorTabItem
import com.itsaky.androidide.plugins.extensions.MenuItem
import com.itsaky.androidide.plugins.extensions.NavigationItem
import com.itsaky.androidide.plugins.extensions.PluginTooltipEntry
import com.itsaky.androidide.plugins.extensions.TabItem
import com.itsaky.androidide.plugins.extensions.UIExtension
import com.itsaky.androidide.plugins.services.IdeEditorTabService
import androidx.fragment.app.Fragment
import org.appdevforall.templatizeproject.fragments.TemplatizeProjectFragment

/**
 * Converts an Android Studio project (under CodeOnTheGoProjects) into a
 * Code On the Go (.cgt) template bundle, and optionally installs it directly
 * into the IDE via IdeTemplateService.
 */
class TemplatizeProjectPlugin : IPlugin, UIExtension, EditorTabExtension, DocumentationExtension {

    companion object {
        private const val TAB_ID = "org_appdevforall_templatizeproject_main"
    }

    private lateinit var context: PluginContext

    override fun initialize(context: PluginContext): Boolean {
        return try {
            this.context = context
            context.logger.info("TemplatizeProjectPlugin initialized successfully")
            true
        } catch (e: Exception) {
            context.logger.error("TemplatizeProjectPlugin initialization failed", e)
            false
        }
    }

    override fun activate(): Boolean {
        context.logger.info("TemplatizeProjectPlugin: Activating plugin")
        return true
    }

    override fun deactivate(): Boolean {
        context.logger.info("TemplatizeProjectPlugin: Deactivating plugin")
        return true
    }

    override fun dispose() {
        context.logger.info("TemplatizeProjectPlugin: Disposing plugin")
    }

    // -- UIExtension --

    override fun getMainMenuItems(): List<MenuItem> = emptyList()

    override fun getEditorTabs(): List<TabItem> = emptyList()

    override fun getSideMenuItems(): List<NavigationItem> {
        return listOf(
            NavigationItem(
                id = "org_appdevforall_templatizeproject_sidebar",
                title = "Templatize Project",
                icon = R.drawable.ic_plugin,
                isEnabled = true,
                isVisible = true,
                group = "tools",
                order = 0,
                action = { openPluginTab() },
            )
        )
    }

    private fun openPluginTab() {
        val editorTabService = context.services.get(IdeEditorTabService::class.java) ?: run {
            context.logger.error("Editor tab service not available")
            return
        }
        if (!editorTabService.isTabSystemAvailable()) {
            context.logger.error("Editor tab system not available")
            return
        }
        try {
            editorTabService.selectPluginTab(TAB_ID)
        } catch (e: Exception) {
            context.logger.error("Error opening Templatize Project tab", e)
        }
    }

    // -- EditorTabExtension --

    override fun getMainEditorTabs(): List<EditorTabItem> {
        return listOf(
            EditorTabItem(
                id = TAB_ID,
                title = "Templatize Project",
                icon = R.drawable.ic_plugin,
                fragmentFactory = { TemplatizeProjectFragment() },
                isCloseable = true,
                isPersistent = false,
                order = 0,
                isEnabled = true,
                isVisible = true,
                tooltip = "Convert an Android project into a Code On the Go template",
            )
        )
    }

    override fun onEditorTabSelected(tabId: String, fragment: Fragment) {}

    override fun onEditorTabClosed(tabId: String) {}

    override fun canCloseEditorTab(tabId: String): Boolean = true

    // -- DocumentationExtension --

    override fun getTooltipCategory(): String = "plugin_templatizeproject"

    override fun getTooltipEntries(): List<PluginTooltipEntry> {
        return listOf(
            PluginTooltipEntry(
                tag = "templatizeproject.overview",
                summary = "<b>Templatize Project</b><br>Convert a project under CodeOnTheGoProjects into a Code On the Go (.cgt) template.",
                detail = """
                    <h3>Templatize Project</h3>
                    <p>Enter the name of a project directory under <code>CodeOnTheGoProjects</code> and a
                    template name. The plugin substitutes concrete values (versions, package name, app
                    name, SDK levels) with Pebble tokens, writes <code>template.json</code> and a
                    thumbnail, and zips the result into a <code>.cgt</code> file. You can then choose to
                    install it directly into Code On the Go's template picker.</p>
                """.trimIndent(),
                buttons = emptyList(),
            )
        )
    }

    override fun onDocumentationInstall(): Boolean = true

    override fun onDocumentationUninstall() {}
}
