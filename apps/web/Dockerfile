FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install --no-audit --no-fund

# Copy application source
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
RUN mkdir -p public
RUN npm run build

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["npm", "run", "start"]
