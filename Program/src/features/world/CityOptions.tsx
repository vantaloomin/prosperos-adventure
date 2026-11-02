import { shelveCities } from './cityText'

interface Option { id: string; name: string; region?: string; category?: string }

/** A city select's options, grouped Real / Modern, Other Eras, Fictional and Custom, each A to Z. */
export function CityOptions({ cities, withRegion = false, featured = [] }: { cities: Option[]; withRegion?: boolean; featured?: Option[] }) {
  const label = (city: Option) => withRegion && city.region ? `${city.name}, ${city.region}` : city.name
  // A featured city is listed again in its own shelf, like a "Recently used" list; keys keep the two apart.
  return (<>
    {featured.length > 0 && <optgroup label="Featured">
      {featured.map((city) => <option key={`featured-${city.id}`} value={city.id}>{label(city)}</option>)}
    </optgroup>}
    {shelveCities(cities).filter((shelf) => shelf.cities.length > 0).map((shelf) => (
      <optgroup key={shelf.id} label={shelf.title}>
        {shelf.cities.map((city) => <option key={city.id} value={city.id}>{label(city)}</option>)}
      </optgroup>
    ))}
  </>)
}
