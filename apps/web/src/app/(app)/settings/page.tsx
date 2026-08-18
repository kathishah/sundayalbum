import ApiKeySettings from '@/components/settings/ApiKeySettings'
import AppearanceSettings from '@/components/settings/AppearanceSettings'
import VersionInfo from '@/components/settings/VersionInfo'

export const metadata = {
  title: 'Settings — Sunday Album',
}

export default function SettingsPage() {
  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-sa-stone-900 dark:text-sa-stone-50 mb-6">
        Settings
      </h1>
      <div className="flex flex-col gap-6">
        <AppearanceSettings />
        <ApiKeySettings />
        <VersionInfo />
      </div>
    </div>
  )
}
