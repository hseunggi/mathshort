FROM eclipse-temurin:21-jdk
WORKDIR /app
COPY . .
RUN ./gradlew clean bootJar -x test
EXPOSE 8080
ENTRYPOINT ["java","-jar","build/libs/api-0.0.1-SNAPSHOT.jar"]
