FROM mcr.microsoft.com/playwright:v1.48.0-jammy

WORKDIR /app

# Copia i file di dipendenze
COPY package*.json ./

# Installa solo le dipendenze (NO devDependencies)
RUN npm install --production

# 🔥 INSTALLA I BROWSER DI PLAYWRIGHT
RUN npx playwright install

# Copia tutto il resto del progetto
COPY . .

# Crea il file DB se non esiste
RUN mkdir -p /app && touch /app/promemoria.db

# Build dell'app Next.js
RUN npm run build

EXPOSE 3000

ENV NODE_ENV=production
ENV PORT=3000

CMD ["npm", "start"]