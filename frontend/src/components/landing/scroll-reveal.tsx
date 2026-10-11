"use client";

import React, { useRef } from "react";
import {
  motion,
  useScroll,
  useSpring,
  useTransform,
  Variants,
} from "motion/react";

interface ScrollRevealProps {
  children: React.ReactNode;
  className?: string;
  delayMs?: number;
  direction?: "up" | "down" | "left" | "right" | "fade" | "scale";
  duration?: number;
  once?: boolean;
}

/**
 * High-performance Motion-driven Scroll Reveal Wrapper
 */
export function ScrollReveal({
  children,
  className = "",
  delayMs = 0,
  direction = "up",
  duration = 0.6,
  once = true,
}: ScrollRevealProps) {
  const getInitialAndAnimate = () => {
    switch (direction) {
      case "up":
        return {
          initial: { opacity: 0, y: 32 },
          whileInView: { opacity: 1, y: 0 },
        };
      case "down":
        return {
          initial: { opacity: 0, y: -28 },
          whileInView: { opacity: 1, y: 0 },
        };
      case "left":
        return {
          initial: { opacity: 0, x: 36 },
          whileInView: { opacity: 1, x: 0 },
        };
      case "right":
        return {
          initial: { opacity: 0, x: -36 },
          whileInView: { opacity: 1, x: 0 },
        };
      case "scale":
        return {
          initial: { opacity: 0, scale: 0.94, y: 20 },
          whileInView: { opacity: 1, scale: 1, y: 0 },
        };
      case "fade":
      default:
        return {
          initial: { opacity: 0 },
          whileInView: { opacity: 1 },
        };
    }
  };

  const { initial, whileInView } = getInitialAndAnimate();

  return (
    <motion.div
      initial={initial}
      whileInView={whileInView}
      viewport={{ once, margin: "-40px" }}
      transition={{
        duration,
        delay: delayMs / 1000,
        ease: [0.16, 1, 0.3, 1], // Smooth luxury cubic-bezier easeOut
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/**
 * Stagger Container for cascading children entrances
 */
interface StaggerContainerProps {
  children: React.ReactNode;
  className?: string;
  staggerDelay?: number;
  delayChildren?: number;
}

export function StaggerContainer({
  children,
  className = "",
  staggerDelay = 0.1,
  delayChildren = 0,
}: StaggerContainerProps) {
  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: staggerDelay,
        delayChildren,
      },
    },
  };

  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-50px" }}
      variants={containerVariants}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 24, scale: 0.98 },
    visible: {
      opacity: 1,
      y: 0,
      scale: 1,
      transition: {
        duration: 0.55,
        ease: [0.16, 1, 0.3, 1],
      },
    },
  };

  return (
    <motion.div variants={itemVariants} className={className}>
      {children}
    </motion.div>
  );
}

/**
 * Parallax Scroll Wrapper
 * Shifts element vertically as user scrolls past it
 */
export function ParallaxWrapper({
  children,
  offset = 40,
  className = "",
}: {
  children: React.ReactNode;
  offset?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });

  const y = useTransform(scrollYProgress, [0, 1], [-offset, offset]);

  return (
    <div ref={ref} className={className}>
      <motion.div style={{ y }} className="w-full h-full">
        {children}
      </motion.div>
    </div>
  );
}

/**
 * Luxury 3D Card Hover Perspective Tilt
 */
export function CardTilt({
  children,
  className = "",
  maxTilt = 6,
}: {
  children: React.ReactNode;
  className?: string;
  maxTilt?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const rotateX = ((y - centerY) / centerY) * -maxTilt;
    const rotateY = ((x - centerX) / centerX) * maxTilt;

    ref.current.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.015, 1.015, 1.015)`;
  };

  const handleMouseLeave = () => {
    if (!ref.current) return;
    ref.current.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)";
  };

  return (
    <div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={`transition-transform duration-200 ease-out will-change-transform ${className}`}
      style={{ transformStyle: "preserve-3d" }}
    >
      {children}
    </div>
  );
}

/**
 * Spring-smoothed Global Scroll Progress Bar displayed at the top of the viewport
 */
export function ScrollProgressBar() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 140,
    damping: 24,
    restDelta: 0.001,
  });

  return (
    <div className="fixed top-0 left-0 right-0 h-[3px] z-50 pointer-events-none bg-transparent">
      <motion.div
        className="h-full origin-left bg-gradient-to-r from-emerald-500 via-teal-400 to-[#143C2E] shadow-sm shadow-emerald-500/40 relative"
        style={{ scaleX }}
      >
        {/* Glowing Head Particle */}
        <div className="absolute right-0 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-emerald-400 blur-[2px] opacity-90 shadow-[0_0_8px_#34D399]" />
      </motion.div>
    </div>
  );
}
