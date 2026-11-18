FROM ubuntu:20.04
# Установка переменных окружения для времени и автоматического режима без подтверждений
ENV TZ=Europe/Moscow
ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:/usr/lib/jvm/java-17-openjdk-amd64/bin:$PATH

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    apt update && apt upgrade -y && apt install wget unzip curl openjdk-17-jdk qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils cpu-checker -y && \
    mkdir /temp && wget https://dl.google.com/android/repository/commandlinetools-linux-8512546_latest.zip -O /temp/AndroidSDKtools.zip && \
    unzip -q /temp/AndroidSDKtools.zip -d /temp && \
    mkdir -p $ANDROID_HOME/cmdline-tools/latest && \
    mv /temp/cmdline-tools/* $ANDROID_HOME/cmdline-tools/latest && \
    chmod +x $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager && \
    yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses --sdk_root=$ANDROID_HOME && \
    $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --update --sdk_root=$ANDROID_HOME && \
    sdkmanager "platform-tools" "platforms;android-35" "system-images;android-35;google_apis;x86_64" "emulator" && \
    echo "no" | avdmanager create avd -n Pixel8ProAPI35 -k "system-images;android-35;google_apis;x86_64"\
    # emulator -avd Pixel8ProAPI35 -no-snapshot-save -gpu auto -no-boot-anim & appium
    # emulator -avd "Pixel8ProAPI35" -noaudio -no-boot-anim -netdelay none -accel on -no-window -no-snapshot -memory 4096 -partition-size 4096
     curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
     apt-get install -y nodejs && \
     npm install -g appium && \
     appium plugin install --global uiautomator2



 # Установка переменных окружения для эмулятора и APK
ENV ANDROID_DEVICE_NAME=Pixel8ProAPI35
ENV APK_PATH=/opt/app.apk

 # Клонирование репозитория
# WORKDIR /app
# RUN git clone https://git.itl.team/unuk/autotests .
#
# # Установка зависимостей Python
# RUN pip3 install --no-cache-dir -r requirements.txt
#
# # Открытие порта Appium
# EXPOSE 4723
#
# #CMD ["bash", "-c", "emulator -avd Pixel8ProAPI35 -no-snapshot-save -gpu auto -no-boot-anim & appium"]
#
#
#
## Установка переменных окружения для эмулятора и APK
#ENV ANDROID_DEVICE_NAME=Pixel8ProAPI35
#ENV APK_PATH=/opt/app.apk
#
## Клонирование репозитория
#WORKDIR /app
#RUN git clone https://git.itl.team/unuk/autotests .
#
## Установка зависимостей Python
#RUN pip3 install --no-cache-dir -r requirements.txt
#
## Открытие порта Appium
#EXPOSE 4723

# Команда по умолчанию для запуска эмулятора и Appium
#CMD ["bash", "-c", "emulator -avd Pixel8ProAPI35 -no-snapshot-save -gpu auto -no-boot-anim & appium"]
