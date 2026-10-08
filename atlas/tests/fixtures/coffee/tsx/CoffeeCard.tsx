export interface CoffeeProps {
  name: string
}

export function label(name: string): string {
  return `Coffee: ${name}`
}

export function CoffeeCard({ name }: CoffeeProps) {
  return <article>{label(name)}</article>
}
