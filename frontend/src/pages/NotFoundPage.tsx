import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <section className="py-16 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link
        to="/dashboard"
        className="mt-4 inline-block text-indigo-600 hover:underline dark:text-indigo-400"
      >
        Back to dashboard
      </Link>
    </section>
  );
}
