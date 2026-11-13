export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="page-shell flex justify-center py-16 sm:py-24">
      <div className="w-full max-w-sm">{children}</div>
    </div>
  );
}
