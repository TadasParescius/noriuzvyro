type ValidationDetail = {field?: string; message?: string};
type ErrorBody = {error?: {code?: string; message?: string; details?: ValidationDetail[]}};

const labels: Record<string, string> = {
  name: 'Pavadinimas', city: 'Miestas', address: 'Adresas', phone: 'Telefonas',
  description: 'Aprašymas', latitude: 'Platuma', longitude: 'Ilguma',
  materialType: 'Medžiaga', fraction: 'Frakcija', pricePerTonneEur: 'Kaina už toną',
  available: 'Prieinamumas', customerName: 'Vardas ir pavardė', email: 'El. paštas',
  password: 'Slaptažodis', deliveryAddress: 'Pristatymo adresas', quantityTonnes: 'Kiekis tonomis',
  willBeHome: 'Ar būsite namuose', unloadingInstructions: 'Išpylimo instrukcija',
  paymentMethod: 'Atsiskaitymo būdas', status: 'Būsena', driverId: 'Vairuotojas', role: 'Rolė',
};

function validationMessage(field: string, message: string): string {
  let match: RegExpMatchArray | null;
  if (message === 'Field required') return 'Užpildykite šį lauką.';
  if ((match = message.match(/^String should have at least (\d+) characters/)))
    return `Įveskite bent ${match[1]} simbolius.`;
  if ((match = message.match(/^String should have at most (\d+) characters/)))
    return `Galima įvesti ne daugiau kaip ${match[1]} simbolių.`;
  if (field === 'phone' && message.startsWith('String should match pattern'))
    return 'Įveskite telefoną tarptautiniu formatu, pvz. +37060000111 (be tarpų).';
  if (message.includes('not a valid email address')) return 'Įveskite tinkamą el. pašto adresą.';
  if ((match = message.match(/^Input should be greater than or equal to (.+)$/)))
    return `Reikšmė turi būti ne mažesnė kaip ${match[1]}.`;
  if ((match = message.match(/^Input should be less than or equal to (.+)$/)))
    return `Reikšmė turi būti ne didesnė kaip ${match[1]}.`;
  if ((match = message.match(/^Input should be greater than (.+)$/)))
    return `Reikšmė turi būti didesnė už ${match[1]}.`;
  if ((match = message.match(/^Input should be a multiple of (.+)$/)))
    return `Reikšmė turi būti ${match[1]} kartotinis.`;
  if (message.includes('Use a JSON number') || message.startsWith('Input should be a valid number') ||
      message.startsWith('Input should be a valid integer') || message.includes('finite number'))
    return 'Įveskite tinkamą skaičių.';
  if (message.startsWith('Input should be a valid boolean')) return 'Pasirinkite taip arba ne.';
  if (message.startsWith('Input should be ')) return 'Pasirinkite vieną iš leidžiamų reikšmių.';
  if (message.includes('Instructions are required when the customer will not be home'))
    return 'Jei nebūsite namuose, nurodykite, kur išpilti medžiagą.';
  if (message.includes('Provide at least one field')) return 'Pakeiskite bent vieną lauką.';
  if (message.includes('Updated fields cannot be null')) return 'Keičiami laukai negali būti tušti.';
  if (message.startsWith('Extra inputs are not permitted')) return 'Šis laukas neleidžiamas.';
  if (message.startsWith('JSON decode error')) return 'Nepavyko perskaityti užklausos duomenų.';
  return message.replace(/^Value error, /, '');
}

export function formatApiError(data: ErrorBody, path = ''): string {
  const error = data.error;
  if (error?.code === 'VALIDATION_ERROR' && Array.isArray(error.details)) {
    const details = error.details.filter(detail => typeof detail?.message === 'string').map(detail => {
      const field = (detail.field || '').replace(/^(body|query|path)\.?/, '');
      const label = field === 'name' && path.split('?')[0] === '/api/auth/register'
        ? 'Vardas ir pavardė' : labels[field] || field || 'Forma';
      return `${label}: ${validationMessage(field, detail.message!)}`;
    });
    if (details.length) return 'Patikrinkite įvestus duomenis:\n' + [...new Set(details)].join('\n');
  }
  if (error?.message === 'Invalid request data.') return 'Patikrinkite, ar visi laukai užpildyti tinkamai.';
  return error?.message || 'Užklausa nepavyko. Bandykite dar kartą.';
}
