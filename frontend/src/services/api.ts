import axios from 'axios';

// La URL base apuntará al backend de FastAPI
// En desarrollo, esto apuntará a localhost:8000
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;
