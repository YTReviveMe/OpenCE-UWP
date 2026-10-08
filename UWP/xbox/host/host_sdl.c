#include "host.h"
#include <SDL.h>
#include <windows.h>
#include <string.h>
#include <stdlib.h>

#define HANDLE_COUNT 256
enum handle_type { HANDLE_FREE, HANDLE_WINDOW, HANDLE_CONTEXT, HANDLE_GAMEPAD, HANDLE_AUDIO };
struct handle { int type; void *object; };
static struct handle handles[HANDLE_COUNT];
static SRWLOCK handle_lock = SRWLOCK_INIT;
static int backbuffer_width = 1920;
static int backbuffer_height = 1080;

void host_sdl_set_backbuffer_size(int width, int height)
{
    if (width > 0 && height > 0) {
        backbuffer_width = width;
        backbuffer_height = height;
    }
}

static uint32_t handle_new(int type, void *object)
{
    uint32_t i;
    if (!object) return 0;
    AcquireSRWLockExclusive(&handle_lock);
    for (i = 1; i < HANDLE_COUNT; ++i) if (handles[i].type == type && handles[i].object == object) break;
    if (i == HANDLE_COUNT) for (i = 1; i < HANDLE_COUNT; ++i) if (!handles[i].type) {
        handles[i].type = type; handles[i].object = object; break;
    }
    ReleaseSRWLockExclusive(&handle_lock);
    return i < HANDLE_COUNT ? i : 0;
}
static void *handle_get(uint32_t value, int type)
{ return value && value < HANDLE_COUNT && handles[value].type == type ? handles[value].object : NULL; }

int GUEST_ABI host_sdl_init(uint32_t flags)
{ return SDL_Init((Uint32)flags) == 0; }
int GUEST_ABI host_sdl_set_hint(const char *name, const char *value)
{ return SDL_SetHint(name, value) == SDL_TRUE; }
void GUEST_ABI host_sdl_get_error(char *buffer, uint32_t size)
{ if (size) SDL_strlcpy(buffer, SDL_GetError(), size); }
int64_t GUEST_ABI host_sdl_ticks(void) { return (int64_t)SDL_GetTicks64(); }
int64_t GUEST_ABI host_sdl_thread_id(void) { return (int64_t)GetCurrentThreadId(); }
void GUEST_ABI host_sdl_scancode_name(int scancode, char *buffer, uint32_t size)
{ if (size) SDL_strlcpy(buffer, SDL_GetScancodeName((SDL_Scancode)scancode), size); }
int GUEST_ABI host_sdl_scancode_from_name(const char *name) { return (int)SDL_GetScancodeFromName(name); }

uint32_t GUEST_ABI host_sdl_create_window(const char *title, int width, int height, int64_t flags)
{
    Uint32 translated = (Uint32)flags;
    return handle_new(HANDLE_WINDOW, SDL_CreateWindow(title, SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        width, height, translated));
}
void GUEST_ABI host_sdl_window_size_in_pixels(uint32_t window, int *width, int *height)
{
    static LONG logged;
    int reported_width = 0, reported_height = 0;
    SDL_GL_GetDrawableSize((SDL_Window *)handle_get(window, HANDLE_WINDOW),
        &reported_width, &reported_height);
    *width = backbuffer_width;
    *height = backbuffer_height;
    if (!InterlockedExchange(&logged, 1))
        host_logf(HOST_LOG_INFO, "SDL drawable reported %dx%d; GL backbuffer is %dx%d",
            reported_width, reported_height, *width, *height);
}
int GUEST_ABI host_sdl_set_relative_mouse(uint32_t window, int enabled)
{ (void)window; return SDL_SetRelativeMouseMode(enabled ? SDL_TRUE : SDL_FALSE) == 0; }
int GUEST_ABI host_sdl_gl_set_attribute(int attribute, int value)
{ return SDL_GL_SetAttribute((SDL_GLattr)attribute, value) == 0; }
uint32_t GUEST_ABI host_sdl_gl_create_context(uint32_t window)
{ return handle_new(HANDLE_CONTEXT, SDL_GL_CreateContext((SDL_Window *)handle_get(window, HANDLE_WINDOW))); }
int GUEST_ABI host_sdl_gl_make_current(uint32_t window, uint32_t context)
{ return SDL_GL_MakeCurrent((SDL_Window *)handle_get(window, HANDLE_WINDOW), handle_get(context, HANDLE_CONTEXT)) == 0; }
int GUEST_ABI host_sdl_gl_set_swap_interval(int interval)
{
    int swap_status = SDL_GL_SetSwapInterval(interval);
    host_logf(swap_status == 0 ? HOST_LOG_INFO : HOST_LOG_WARN,
        "Xbox presentation: swap interval %d %s%s%s", interval,
        swap_status == 0 ? "accepted" : "rejected",
        swap_status == 0 ? "" : ": ", swap_status == 0 ? "" : SDL_GetError());
    return swap_status == 0;
}
int GUEST_ABI host_sdl_gl_swap_window(uint32_t window)
{
    static LARGE_INTEGER frequency;
    static LARGE_INTEGER started;
    static unsigned long frames;
    LARGE_INTEGER now;

    SDL_GL_SwapWindow((SDL_Window *)handle_get(window, HANDLE_WINDOW));
    if (!frequency.QuadPart) {
        QueryPerformanceFrequency(&frequency);
        QueryPerformanceCounter(&started);
    }
    frames++;
    QueryPerformanceCounter(&now);
    if (now.QuadPart - started.QuadPart >= frequency.QuadPart * 5) {
        double seconds = (double)(now.QuadPart - started.QuadPart) / (double)frequency.QuadPart;
        host_logf(HOST_LOG_INFO, "Xbox presentation: %.1f FPS (%lu frames in %.2f seconds)",
            (double)frames / seconds, frames, seconds);
        started = now;
        frames = 0;
    }
    return 1;
}

int GUEST_ABI host_sdl_poll_event(void *output)
{
    SDL_Event event;
    unsigned char *out = (unsigned char *)output;
    while (SDL_PollEvent(&event)) {
        memset(out, 0, 128);
        if (event.type == SDL_QUIT) { *(uint32_t *)out = 0x100; return 1; }
        if (event.type == SDL_CONTROLLERDEVICEADDED || event.type == SDL_CONTROLLERDEVICEREMOVED ||
            event.type == SDL_CONTROLLERDEVICEREMAPPED) {
            *(uint32_t *)out = event.type;
            *(uint64_t *)(out + 8) = (uint64_t)event.cdevice.timestamp * 1000000ULL;
            *(int32_t *)(out + 16) = event.cdevice.which;
            return 1;
        }
        if (event.type == SDL_WINDOWEVENT) {
            uint32_t type = 0;
            if (event.window.event == SDL_WINDOWEVENT_FOCUS_GAINED) type = 0x20e;
            else if (event.window.event == SDL_WINDOWEVENT_FOCUS_LOST) type = 0x20f;
            else if (event.window.event == SDL_WINDOWEVENT_CLOSE) type = 0x210;
            if (type) { *(uint32_t *)out = type; return 1; }
        }
    }
    return 0;
}

int GUEST_ABI host_sdl_get_gamepads(uint32_t *ids, int capacity)
{
    int found = 0, count = SDL_NumJoysticks(), i;
    for (i = 0; i < count && found < capacity; ++i)
        if (SDL_IsGameController(i)) ids[found++] = (uint32_t)SDL_JoystickGetDeviceInstanceID(i);
    return found;
}
static SDL_GameController *controller_from_instance(SDL_JoystickID id)
{
    SDL_GameController *controller = SDL_GameControllerFromInstanceID(id);
    int i;
    if (controller) return controller;
    for (i = 0; i < SDL_NumJoysticks(); ++i)
        if (SDL_IsGameController(i) && SDL_JoystickGetDeviceInstanceID(i) == id)
            return SDL_GameControllerOpen(i);
    return NULL;
}
uint32_t GUEST_ABI host_sdl_open_gamepad(uint32_t id)
{ return handle_new(HANDLE_GAMEPAD, controller_from_instance((SDL_JoystickID)id)); }
uint32_t GUEST_ABI host_sdl_gamepad_from_id(uint32_t id)
{ return handle_new(HANDLE_GAMEPAD, controller_from_instance((SDL_JoystickID)id)); }
int GUEST_ABI host_sdl_gamepad_axis(uint32_t gamepad, int axis)
{ SDL_GameController *c = (SDL_GameController *)handle_get(gamepad, HANDLE_GAMEPAD); return c ? SDL_GameControllerGetAxis(c, (SDL_GameControllerAxis)axis) : 0; }
int GUEST_ABI host_sdl_gamepad_button(uint32_t gamepad, int button)
{ SDL_GameController *c = (SDL_GameController *)handle_get(gamepad, HANDLE_GAMEPAD); return c ? SDL_GameControllerGetButton(c, (SDL_GameControllerButton)button) : 0; }
int GUEST_ABI host_sdl_gamepad_type(uint32_t gamepad)
{ SDL_GameController *c = (SDL_GameController *)handle_get(gamepad, HANDLE_GAMEPAD); return c ? (int)SDL_GameControllerGetType(c) : 0; }
int GUEST_ABI host_sdl_rumble_gamepad(uint32_t gamepad, uint32_t low, uint32_t high, uint32_t ms)
{ SDL_GameController *c = (SDL_GameController *)handle_get(gamepad, HANDLE_GAMEPAD); return c && SDL_GameControllerRumble(c, (Uint16)low, (Uint16)high, ms) == 0; }

struct guest_audio_spec { uint32_t format; int channels; int frequency; };
struct audio_binding {
    SDL_AudioDeviceID device;
    uint32_t callback, userdata, handle;
    unsigned char *data;
    int length, capacity;
    int float_to_s16;
};
static __declspec(thread) struct audio_binding *audio_calling;
static void SDLCALL audio_callback(void *opaque, Uint8 *stream, int length)
{
    struct audio_binding *binding = (struct audio_binding *)opaque;
    int guest_length = binding->float_to_s16 ? length * 2 : length;
    memset(stream, 0, length); binding->length = 0; audio_calling = binding;
    if (binding->callback)
        host_call_guest(binding->callback, binding->userdata, binding->handle, (uint32_t)guest_length, 0);
    audio_calling = NULL;
    if (binding->float_to_s16) {
        const float *source = (const float *)binding->data;
        Sint16 *destination = (Sint16 *)stream;
        int samples = binding->length / (int)sizeof(float);
        int capacity = length / (int)sizeof(Sint16);
        int sample;
        if (samples > capacity) samples = capacity;
        for (sample = 0; sample < samples; ++sample) {
            float value = source[sample];
            destination[sample] = value >= 1.0f ? 32767 :
                value <= -1.0f ? -32768 : (Sint16)(value * 32767.0f);
        }
    } else {
        if (binding->length > length) binding->length = length;
        if (binding->length) memcpy(stream, binding->data, binding->length);
    }
}
uint32_t GUEST_ABI host_sdl_open_audio_stream(uint32_t device, const void *spec_ptr, uint32_t callback, uint32_t userdata)
{
    const struct guest_audio_spec *spec = (const struct guest_audio_spec *)spec_ptr;
    struct audio_binding *binding = (struct audio_binding *)calloc(1, sizeof(*binding));
    SDL_AudioSpec wanted, obtained;
    char first_error[256];
    (void)device;
    if (!binding) return 0;
    SDL_zero(wanted); wanted.freq = spec->frequency; wanted.format = spec->format;
    wanted.channels = spec->channels; wanted.samples = 1024; wanted.callback = audio_callback; wanted.userdata = binding;
    binding->callback = callback; binding->userdata = userdata;
    host_logf(HOST_LOG_INFO, "Xbox audio: requested %d Hz, %d channels, format %04x",
        spec->frequency, spec->channels, (unsigned)spec->format);
    SDL_zero(obtained);
    binding->device = SDL_OpenAudioDevice(NULL, 0, &wanted, &obtained, 0);
    if (!binding->device && spec->format == AUDIO_F32SYS) {
        SDL_strlcpy(first_error, SDL_GetError(), sizeof(first_error));
        wanted.format = AUDIO_S16SYS;
        binding->device = SDL_OpenAudioDevice(NULL, 0, &wanted, &obtained, 0);
        if (binding->device) {
            binding->float_to_s16 = 1;
            host_logf(HOST_LOG_INFO,
                "Xbox audio: float output rejected (%s); using %d Hz, %u-channel signed 16-bit PCM",
                first_error, obtained.freq, (unsigned)obtained.channels);
        }
    }
    if (!binding->device) {
        host_logf(HOST_LOG_WARN, "Xbox audio: exact PCM open failed (%s); trying device negotiation",
            SDL_GetError());
        wanted.format = AUDIO_S16SYS;
        SDL_zero(obtained);
        binding->device = SDL_OpenAudioDevice(NULL, 0, &wanted, &obtained,
            SDL_AUDIO_ALLOW_ANY_CHANGE);
        if (binding->device && obtained.format == AUDIO_S16SYS &&
                obtained.channels == spec->channels && obtained.freq == spec->frequency) {
            binding->float_to_s16 = 1;
            host_logf(HOST_LOG_INFO, "Xbox audio: negotiated %d Hz, %u-channel signed 16-bit PCM",
                obtained.freq, (unsigned)obtained.channels);
        } else if (binding->device) {
            host_logf(HOST_LOG_ERROR, "Xbox audio: unsupported negotiated format %d Hz, %u channels, %04x",
                obtained.freq, (unsigned)obtained.channels, (unsigned)obtained.format);
            SDL_CloseAudioDevice(binding->device);
            binding->device = 0;
        }
    }
    if (!binding->device) { free(binding); return 0; }
    if (!binding->float_to_s16)
        host_logf(HOST_LOG_INFO, "Xbox audio: opened %d Hz, %u channels, format %04x",
            obtained.freq, (unsigned)obtained.channels, (unsigned)obtained.format);
    binding->handle = handle_new(HANDLE_AUDIO, binding);
    return binding->handle;
}
int GUEST_ABI host_sdl_put_audio_stream_data(uint32_t stream, const void *data, int length)
{
    struct audio_binding *binding = (struct audio_binding *)handle_get(stream, HANDLE_AUDIO);
    if (!binding || binding != audio_calling || length < 0) return 0;
    if (length > binding->capacity) {
        void *resized = realloc(binding->data, length);
        if (!resized) return 0;
        binding->data = (unsigned char *)resized; binding->capacity = length;
    }
    memcpy(binding->data, data, length); binding->length = length; return 1;
}
int GUEST_ABI host_sdl_resume_audio_stream_device(uint32_t stream)
{ struct audio_binding *b = (struct audio_binding *)handle_get(stream, HANDLE_AUDIO); if (!b) return 0; SDL_PauseAudioDevice(b->device, 0); return 1; }

int GUEST_ABI host_sdl_set_clipboard_text(const char *text) { return SDL_SetClipboardText(text) == 0; }
void GUEST_ABI host_sdl_get_clipboard_text(char *buffer, uint32_t size)
{ char *text = SDL_GetClipboardText(); if (size) SDL_strlcpy(buffer, text ? text : "", size); SDL_free(text); }
int GUEST_ABI host_sdl_show_toast(const char *message, int duration, int gravity, int x, int y)
{ (void)message; (void)duration; (void)gravity; (void)x; (void)y; return 0; }
int GUEST_ABI host_sdl_show_simple_message_box(uint32_t flags, const char *title, const char *message)
{ return SDL_ShowSimpleMessageBox(flags, title, message, NULL) == 0; }
