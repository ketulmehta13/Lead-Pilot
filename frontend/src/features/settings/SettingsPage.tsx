import { PageHeader } from '../../components/ui/misc';
import { useAuth } from '../auth/AuthContext';
import { AppearanceSection, PasswordSection, ProfileSection } from './AccountSections';
import { SystemSection, TeamSection } from './AdminSections';

/** Profile, password and appearance for everyone; team and system status for admins. */
export function SettingsPage() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole('admin');
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Settings"
        description={
          isAdmin
            ? 'Your account, the team and how LeadPilot is connected.'
            : 'Your account and preferences.'
        }
      />
      <div className="space-y-6">
        <ProfileSection />
        <PasswordSection />
        <AppearanceSection />
        {isAdmin && (
          <>
            <TeamSection />
            <SystemSection />
          </>
        )}
      </div>
    </div>
  );
}
