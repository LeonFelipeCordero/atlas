import { CoffeeCard, label } from './CoffeeCard'
import * as Cards from './CoffeeCard'

export function App() {
  return (
    <main>
      <CoffeeCard name={label('espresso')} />
      <Cards.CoffeeCard name="latte"></Cards.CoffeeCard>
    </main>
  )
}

// A prop with the same name is not evidence for the imported component.
export function Preview({ CoffeeCard }: { CoffeeCard: typeof Cards.CoffeeCard }) {
  return <CoffeeCard name="preview" />
}
