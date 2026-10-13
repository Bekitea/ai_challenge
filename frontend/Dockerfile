# Сборка React-фронтенда и раздача через nginx.
# nginx проксирует /api на сервис web (см. nginx.conf), поэтому браузер
# работает с одним origin и заголовок Authorization проходит как есть.
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
