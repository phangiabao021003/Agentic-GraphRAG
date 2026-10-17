FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
# npm install, not npm ci: the Windows-generated lockfile omits Linux-only
# optional deps (@emnapi/* wasm fallbacks) and npm ci refuses to proceed.
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
