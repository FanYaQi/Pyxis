import Link from "next/link";
import Image from "next/image";

export default function Logo() {
  return (
    <Link href="/" className="inline-flex" aria-label="Pyxis">
      {/* font logo is in Fira Code */}
      <Image
        src="/images/pyxis-text.svg"
        alt="Pyxis Text"
        width={150}
        height={40}
      />
    </Link>
  );
}
