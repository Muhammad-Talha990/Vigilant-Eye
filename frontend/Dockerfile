# Multi-stage production frontend (static assets via nginx).
# Development continues to use docker-compose.yml + Vite.
#
# Demo login shortcuts are OFF in this image (production build).
# To bake demo helpers into a special image: --build-arg VITE_ENABLE_DEMO_HELPERS=1

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ARG VITE_API_URL=http://127.0.0.1:8000
ARG VITE_ENABLE_DEMO_HELPERS=0
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_ENABLE_DEMO_HELPERS=$VITE_ENABLE_DEMO_HELPERS
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
