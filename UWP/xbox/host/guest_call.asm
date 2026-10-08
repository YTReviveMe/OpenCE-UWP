; Enter x32 System V guest code from a Windows x64 host. The fifth and sixth
; parameters are the fourth guest argument and the top of a low (<4 GB) stack.
PUBLIC host_enter_guest
.code
host_enter_guest PROC
    mov eax, DWORD PTR [rsp+40]
    mov r10, QWORD PTR [rsp+48]
    push rbx
    push rbp
    push rdi
    push rsi
    push r12
    push r13
    push r14
    push r15
    mov r11, rsp
    and r10, -16
    sub r10, 16
    mov QWORD PTR [r10+8], r11
    mov r11, rcx
    mov edi, edx
    mov esi, r8d
    mov edx, r9d
    mov ecx, eax
    mov rsp, r10
    call r11
    mov rsp, QWORD PTR [rsp+8]
    pop r15
    pop r14
    pop r13
    pop r12
    pop rsi
    pop rdi
    pop rbp
    pop rbx
    ret
host_enter_guest ENDP
END
