services:
  subtitle:
    image: edwinzzz888/subtitle:latest
    container_name: subtitle-app
    ports:
      - "5000:5000"
    volumes:
      - ./videos:/app/videos
      - ./test_videos:/app/test_videos
      - ./config:/app/config
    environment:
      - FLASK_ENV=production
    restart: unless-stopped
    networks:
      - subtitle-network

networks:
  subtitle-network:
    driver: bridge