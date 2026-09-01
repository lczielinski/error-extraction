#lang s-exp herbie/syntax/platform-language

;;; The operators costex and Daisy's rewriter can express: +, -, *, /, neg,
;;; sqrt, PI and E, over binary64 and binary32.  Herbie's own platforms carry
;;; the whole of libm, so it would answer with fma, hypot, expm1 and friends --
;;; programs the other two rewriters cannot reach and this benchmark cannot
;;; evaluate.  Restricting the platform keeps the three searching one language.
;;;
;;; The costs are c.rkt's, which come from a real machine; only the operations
;;; are dropped.

(require math/flonum)

(define bool-move 0.0233)
(define move32 0.0625)
(define move64 0.0933)

;;;;;;;;;;;;;;;;;;;;;;;;;;;;; BOOLEAN ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

(define-representation <bool> #:cost bool-move)

(define-operations () <bool>
  [TRUE  #:spec (TRUE)  #:impl (const true)  #:fpcore TRUE  #:cost bool-move]
  [FALSE #:spec (FALSE) #:impl (const false) #:fpcore FALSE #:cost bool-move])

(define-operations ([x <bool>] [y <bool>]) <bool>
  [and #:spec (and x y) #:impl (lambda v (andmap values v)) #:cost bool-move]
  [or  #:spec (or x y)  #:impl (lambda v (ormap values v))  #:cost bool-move])

(define-operation (not [x <bool>]) <bool>
  #:spec (not x) #:impl not #:cost bool-move)

;;;;;;;;;;;;;;;;;;;;;;;;;;;;; BINARY 32 ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

(define-representation <binary32> #:cost move32)

(define-operation (if.f32 [c <bool>] [t <binary32>] [f <binary32>]) <binary32>
  #:spec (if c t f) #:impl if-impl
  #:cost (if-cost bool-move))

(define-operations ([x <binary32>] [y <binary32>]) <bool>
  [==.f32 #:spec (== x y) #:impl =          #:cost move32]
  [!=.f32 #:spec (!= x y) #:impl (negate =) #:cost move32]
  [<.f32  #:spec (< x y)  #:impl <          #:cost move32]
  [>.f32  #:spec (> x y)  #:impl >          #:cost move32]
  [<=.f32 #:spec (<= x y) #:impl <=         #:cost move32]
  [>=.f32 #:spec (>= x y) #:impl >=         #:cost move32])

(define-operations () <binary32> #:fpcore (! :precision binary32 _)
  [PI.f32 #:spec (PI) #:impl (const (flsingle pi))      #:fpcore PI #:cost move32]
  [E.f32  #:spec (E)  #:impl (const (flsingle (exp 1))) #:fpcore E  #:cost move32])

(define-operation (neg.f32 [x <binary32>]) <binary32>
  #:spec (neg x) #:impl (compose flsingle -)
  #:fpcore (! :precision binary32 (- x)) #:cost 0.125)

(define-operations ([x <binary32>] [y <binary32>]) <binary32>
  #:fpcore (! :precision binary32 _)
  [+.f32 #:spec (+ x y) #:impl (compose flsingle +) #:cost 0.200]
  [-.f32 #:spec (- x y) #:impl (compose flsingle -) #:cost 0.200]
  [*.f32 #:spec (* x y) #:impl (compose flsingle *) #:cost 0.250]
  [/.f32 #:spec (/ x y) #:impl (compose flsingle /) #:cost 0.350])

(define-operation (sqrt.f32 [x <binary32>]) <binary32>
  #:spec (sqrt x) #:impl (compose flsingle flsqrt)
  #:fpcore (! :precision binary32 (sqrt x)) #:cost 0.250)

;;;;;;;;;;;;;;;;;;;;;;;;;;;;; BINARY 64 ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

(define-representation <binary64> #:cost move64)

(define-operation (if.f64 [c <bool>] [t <binary64>] [f <binary64>]) <binary64>
  #:spec (if c t f) #:impl if-impl
  #:cost (if-cost bool-move))

(define-operations ([x <binary64>] [y <binary64>]) <bool>
  [==.f64 #:spec (== x y) #:impl =          #:cost move64]
  [!=.f64 #:spec (!= x y) #:impl (negate =) #:cost move64]
  [<.f64  #:spec (< x y)  #:impl <          #:cost move64]
  [>.f64  #:spec (> x y)  #:impl >          #:cost move64]
  [<=.f64 #:spec (<= x y) #:impl <=         #:cost move64]
  [>=.f64 #:spec (>= x y) #:impl >=         #:cost move64])

(define-operations () <binary64> #:fpcore (! :precision binary64 _)
  [PI.f64 #:spec (PI) #:impl (const pi)      #:fpcore PI #:cost move64]
  [E.f64  #:spec (E)  #:impl (const (exp 1)) #:fpcore E  #:cost move64])

(define-operation (neg.f64 [x <binary64>]) <binary64>
  #:spec (neg x) #:impl -
  #:fpcore (! :precision binary64 (- x)) #:cost 0.0966)

(define-operations ([x <binary64>] [y <binary64>]) <binary64>
  #:fpcore (! :precision binary64 _)
  [+.f64 #:spec (+ x y) #:impl + #:cost 0.1646]
  [-.f64 #:spec (- x y) #:impl - #:cost 0.1516]
  [*.f64 #:spec (* x y) #:impl * #:cost 0.2087]
  [/.f64 #:spec (/ x y) #:impl / #:cost 0.2662])

(define-operation (sqrt.f64 [x <binary64>]) <binary64>
  #:spec (sqrt x) #:impl flsqrt
  #:fpcore (! :precision binary64 (sqrt x)) #:cost 0.2216)
